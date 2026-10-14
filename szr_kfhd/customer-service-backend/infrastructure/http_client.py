# itwwy/infrastructure/http_client.py
"""
httpx 和 requests 是同一类东西——都是 Python 的 HTTP 客户端库，干一样的活：发 GET/POST、带请求
头、传参数、处理响应。你平时怎么用 requests，httpx 基本就怎么用，它的 API 就是照着 requests 设计
的，httpx.get()、r.json() 这些写法几乎可以无缝互换
"""
import asyncio

from httpx import AsyncClient

# 全局变量：整个程序共享这一个客户端实例
http_client: AsyncClient | None = None


# 初始化
def init_http_client():
    global http_client
    http_client = AsyncClient(timeout=10.0)


# 关闭
async def close_http_client():
    if http_client is not None:
        await http_client.aclose()


if __name__ == '__main__':
    async def test():
        init_http_client()
        # http://localhost:18081/docs
        result = await http_client.get('http://localhost:18081/users/u1001/orders')
        # --------新增2行，其余不动--------
        if result.status_code >= 400:
            print("响应错误，原始返回:", repr(result.text))
        else:
            print(result.json())
        # --------------------------------

        await close_http_client()


    asyncio.run(test())

"""
#同步方式
# r = httpx.get('http://localhost:18081/users/u1001/orders')
# print(r.json())

#异步方式
# async def test():
#     async with httpx.AsyncClient() as client:
#         r = await client.get('http://localhost:18081/users/u1001/orders')
#         print(r.json()['data']['user_id'])
# asyncio.run(test())
"""
