from pathlib import Path
from dataclasses import dataclass
from omegaconf import OmegaConf
# 定义配置路径   Path(__file__).parents[1] / 'conf' / 'text_config.yaml'
config_file=Path(__file__).parents[2]/'conf'/'text_config.yaml'
conf=OmegaConf.load(config_file)

# print(conf['name'])

@dataclass
class FileConfig:
    enable:bool
    level:str

# 定义封装实体
@dataclass
class AppConfig:
    name: str
    age: int
    height: float
    file: FileConfig

# 创建封装结构
schema=OmegaConf.structured(AppConfig)
# 封装配置内容到配置对象中
app_config:AppConfig = OmegaConf.to_object(OmegaConf.merge(schema,conf))
# 获取配置数据
print(app_config.name)