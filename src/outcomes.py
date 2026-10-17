"""Fail-closed stage errors and cancellation-safe ownership of parallel work."""

import asyncio


class StageFailure(RuntimeError):
    def __init__(self, stage, context, cause):
        self.stage, self.context = stage, context
        # Do not expose provider messages, which can contain credentials/inputs.
        super().__init__(f"{stage} failed [{context}] ({type(cause).__name__})")


async def gather_owned(*operations):
    tasks = [asyncio.create_task(operation) for operation in operations]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
