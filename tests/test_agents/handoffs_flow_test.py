import uuid
import selectors
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.agents.handoffs.travel_agent import create_travel_agent
import asyncio

async def  run_interactive_chat():
    """
    运行持续对话的测试循环
    :return:
    """
    # 1.生成一个唯一的会话id(thread_id)
    #langraph 的checkpointer 需要这个id来区分不同的会话历史

    travel_agent = await create_travel_agent()

    thread_id = str(uuid.uuid4())
    config = {'configurable':{'thread_id':thread_id}}
    print(f'开始测试  会话id：{thread_id}')
    print('输入q quit exit退出会话')
    print('-'*50)

    while True:
        try:
             ## 获取用户输入
            user_input = input('\nuser(你)：').strip()

            if not user_input:
                continue
            if user_input.lower() in ['q','quit','exit']:
                print('结束对话')
                break
            # 构造输入状态
            inputs = {'messages':[HumanMessage(content=user_input)]}
            print('\nAssistant(Agent):',end='',flush=True)
            last_message_id = None
            async for event in travel_agent.astream(inputs,config=config,stream_mode = 'values'):
                #获取当前状态下的消息列表
                messages = event.get('messages',[])
                if messages:
                    last_msg = messages[-1]
                    if last_msg.id == last_message_id:
                        continue
                    last_message_id = last_msg.id

                    if isinstance(last_msg,AIMessage) and last_msg.content:
                        print(last_msg.content)
                    elif isinstance(last_msg,ToolMessage):
                        print(f'\n[系统日志]工具执行完毕:{last_msg.name}')

        except Exception as e:
            print(f"\n❌ 发生错误66: {e}")
            import traceback
            traceback.print_exc()
if __name__ == "__main__":
    asyncio.run(
        run_interactive_chat(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
