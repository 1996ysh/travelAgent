import os

from dotenv import load_dotenv
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage

load_dotenv()

def test():
    print('test')

    try:
        model = ChatTongyi(
            model='qwen-plus',
            api_key=os.getenv('DASHSCOPE_API_KEY'),
            temperature  = 0.7,
        )
        invoke = model.invoke([HumanMessage(content='你好，请用一句话介绍你自己')])
        print(f'response:{invoke.content}')
    except Exception as e :
        print("连接失败")
        raise


if __name__ == "__main__":
    test()
