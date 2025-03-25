import os
import chardet
from dataclasses import dataclass

from pydantic import BaseModel, Field

from pydantic_ai import Agent, RunContext


@dataclass
class CodeBlock:
    content: str
    file_path: str
    function_name: str


class DatabaseConn:
    """This is a fake database for example purposes.

    In reality, you'd be connecting to an external database
    (e.g. PostgreSQL) to get information.
    """

    @classmethod
    async def get_code_blocks(cls, *, path: str) -> list[CodeBlock]:
        files = [
            os.path.join(path, f)
            for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
        ]

        code_blocks = []
        for f in files:
            with open(f, "rb") as file:
                raw_data = file.read()
                result = chardet.detect(raw_data)
                encoding = result["encoding"]
                decoded_data = raw_data.decode(encoding)
                new_lines = [
                    line for line in decoded_data.splitlines() if line.startswith("+")
                ]
                code_blocks.append(
                    CodeBlock(
                        content="\n".join(new_lines),
                        file_path=f,
                        function_name=f.split("/")[-1].split(".")[0],
                    )
                )
        return code_blocks


@dataclass
class SupportDependencies:
    db: DatabaseConn
    files_path: str
    code_blocks: list[CodeBlock]
    code_block_index: int = Field(
        default=0, description="The index of the code block to use"
    )


class SupportResult(BaseModel):
    support_advice: str = Field(description="Advice returned to the customer")
    block_card: bool = Field(description="Whether to block the customer's card")
    risk: int = Field(description="Risk level of query", ge=0, le=10)


bdi = Agent(
    "openai:gpt-4o",
    deps_type=SupportDependencies,
    result_type=SupportResult,
    system_prompt=(
        "You're a seasoned professional in software documentation. "
        "Your expertise lies in breaking down complex technical concepts into "
        "easy-to-understand documentation. You have a passion for clarity and "
        "precision, and you take pride in creating documentation that helps users "
        "and developers alike. Your background in software engineering gives you a "
        "deep understanding of the topics you document, making your work invaluable "
        "to your team."
    ),
)


@bdi.system_prompt
async def current_code_block(ctx: RunContext[SupportDependencies]) -> str:
    """Returns the current code block."""
    return f"The current code block is: {ctx.deps.code_blocks[ctx.deps.code_block_index]!r}"


@bdi.tool
async def update_code_block_index(
    ctx: RunContext[SupportDependencies], code_block_index: int
) -> str:
    """Updates the index of the code block to use."""
    ctx.deps.code_block_index = code_block_index
    return f"The code block index is: {ctx.deps.code_block_index!r}"


@bdi.tool
async def get_code_block(ctx: RunContext[SupportDependencies]) -> str:
    """Gets the code block at the current index."""
    return ctx.deps.code_blocks[ctx.deps.code_block_index]


async def main():
    deps = SupportDependencies(
        files_path="./files", db=DatabaseConn(), code_blocks=[], code_block_index=0
    )
    code_blocks = await deps.db.get_code_blocks(path=deps.files_path)
    deps.code_blocks = code_blocks

    result1 = await bdi.run(
        "Give a binary response to this question. Does this function have a documentation string?",
        deps=deps,
    )
    print(result1.data)

    result2 = await bdi.run(
        "Give a score of 0 through 100 of a code documentation.",
        deps=deps,
        message_history=result1.new_messages(),
    )
    print(result2.data)

    result3 = await bdi.run(
        "Write concise documentations of function level.",
        deps=deps,
        message_history=[*result1.new_messages(), *result2.new_messages()],
    )
    print(result3.data)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
