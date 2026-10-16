#!/usr/bin/env bash
# =============================================================================
# 在腾讯云轻量 2C2G 服务器上一键部署 octop（SQLite 模式，低内存构建）
# 用法：root 登录网页终端后，把本文件内容粘贴执行即可（交互式填密码/密钥）
# 前置：安全组/防火墙先放通 22、8088（控制台 → 防火墙 → 添加规则）
# =============================================================================
set -e
export DEBIAN_FRONTEND=noninteractive

# 防呆：必须 root 运行
if [ "$(id -u)" != "0" ]; then
  echo "!! 请先用 sudo -i 切到 root 再运行本脚本"; exit 1
fi

echo "========== [1/7] 系统检查 =========="
. /etc/os-release
echo "系统: $PRETTY_NAME | 架构: $(uname -m)"
free -h
df -h / | tail -1
if [ "$ID" != "ubuntu" ]; then
  echo "!! 本脚本按 Ubuntu 写，当前是 $ID，后续 apt 步骤可能不适用，请谨慎。"
fi

echo "========== [2/7] 换腾讯云 apt 镜像（加速，兼容 22.04/24.04+/26.04） =========="
mirror_apt() {
  local M=https://mirrors.cloud.tencent.com/ubuntu
  local P='s|http://archive.ubuntu.com/ubuntu|'"$M"'|g; s|http://security.ubuntu.com/ubuntu|'"$M"'|g; s|https://archive.ubuntu.com/ubuntu|'"$M"'|g; s|https://security.ubuntu.com/ubuntu|'"$M"'|g'
  [ -f /etc/apt/sources.list ] && sed -i "$P" /etc/apt/sources.list
  # Ubuntu 24.04/26.04 用 deb822 格式，文件在 sources.list.d/ubuntu.sources
  [ -f /etc/apt/sources.list.d/ubuntu.sources ] && sed -i "$P" /etc/apt/sources.list.d/ubuntu.sources
}
mirror_apt
apt-get update -y

echo "========== [3/7] 安装 git + Docker（腾讯云镜像，失败回退官方源） =========="
apt-get install -y git ca-certificates curl gnupg
install_docker() {
  if command -v docker >/dev/null 2>&1; then echo "docker 已安装"; return; fi
  echo "尝试腾讯云镜像装 docker..."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -y && apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin && systemctl enable --now docker
  if ! command -v docker >/dev/null 2>&1; then
    echo "腾讯镜像失败，回退官方脚本..."
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && sh /tmp/get-docker.sh
    systemctl enable --now docker
  fi
}
install_docker
docker --version
docker compose version

echo "========== [4/7] 配置 Docker 镜像加速 + 日志限制 =========="
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.m.daocloud.io"
  ],
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "3" }
}
JSON
systemctl restart docker

echo "========== [5/7] 创建 4G swap（2G 内存保命） =========="
if [ ! -f /swapfile ]; then
  fallocate -l 4G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=4096
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
free -h

echo "========== [6/7] 部分克隆 octop_two（避开仓库里的大文件） =========="
cd /root
if [ ! -d showreel/.git ]; then
  # --filter=blob:none + sparse：只拉需要的 blob，不碰仓库里的大文件
  git clone --filter=blob:none --sparse -b gbb-sync https://github.com/martinkalcheva-lgtm/showreel.git
fi
cd /root/showreel
git sparse-checkout set octop_two deploy_octop.sh
cd /root/showreel/octop_two

# 交互式收集敏感信息（不写死弱密码）
read -r -p "输入 octop 管理员密码（字母+数字，>=8位）: " OCTOP_PW
read -r -p "输入 DashScope API Key（通义千问嵌入，留空则稍后在界面配）: " DASH_KEY
cat > docker/.env <<ENV
OCTOP_PORT=8088
OCTOP_LOG_LEVEL=info
OCTOP_ADMIN_USERNAME=admin
OCTOP_DEFAULT_PASSWORD=${OCTOP_PW}
OCTOP_DATABASE_SQLITE_PATH=octop.db
DASHSCOPE_API_KEY=${DASH_KEY}
LANGFUSE_TRACING_ENABLED=false
ENV
echo "docker/.env 已生成（密码未回显，已写入文件）"

echo "========== [7/7] 低内存构建并启动 octop =========="
cd /root/showreel/octop_two
docker compose -f docker/docker-compose.yml build \
  --build-arg PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
  --build-arg PIP_TRUSTED_HOST=mirrors.cloud.tencent.com \
  --build-arg NPM_REGISTRY=https://mirrors.cloud.tencent.com/npm/ \
  --build-arg APT_MIRROR=mirrors.cloud.tencent.com \
  --build-arg NODE_MAX_OLD_SPACE_SIZE=1024
docker compose -f docker/docker-compose.yml up -d

echo "========== 等 40 秒看状态 =========="
sleep 40
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}'
free -h
echo "访问地址: http://62.234.56.90:8088  （记得控制台防火墙放通 8088）"
echo "若 docker ps 里 octop 状态为 Restarting/Unhealthy，执行: docker logs octop --tail 50"
