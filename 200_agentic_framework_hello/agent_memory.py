from pydantic import BaseModel


class UserInfo(BaseModel):
    name: str | None = None
    age: int | None = None


from collections.abc import MutableSequence, Sequence
from typing import Any

import builtins

from agent_framework import (
    ContextProvider,
    Context,
    ChatAgent,
    ChatClientProtocol,
    ChatMessage,
    ChatOptions,
)


class UserInfoMemory(ContextProvider):
    def __init__(
        self,
        chat_client: ChatClientProtocol,
        user_info: UserInfo | None = None,
        **kwargs: Any,
    ):
        """Create the memory.

        If you pass in kwargs, they will be attempted to be used to create a UserInfo object.
        """
        self._chat_client = chat_client
        if user_info:
            self.user_info = user_info
        elif kwargs:
            self.user_info = UserInfo.model_validate(kwargs)
        else:
            self.user_info = UserInfo()

    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        invoke_exception: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Extract user information from messages after each agent call."""
        # Ensure request_messages is a list
        messages_list = (
            [request_messages]
            if isinstance(request_messages, ChatMessage)
            else builtins.list(request_messages)
        )

        # Check if we need to extract user info from user messages
        user_messages = [msg for msg in messages_list if msg.role.value == "user"]

        if (
            self.user_info.name is None or self.user_info.age is None
        ) and user_messages:
            try:
                # Use the chat client to extract structured information
                result = await self._chat_client.get_response(
                    messages=messages_list,
                    chat_options=ChatOptions(
                        instructions=(
                            "Extract the user's name and age from the message if present. "
                            "If not present return nulls."
                        ),
                        response_format=UserInfo,
                    ),
                )

                # Update user info with extracted data
                if result.value and isinstance(result.value, UserInfo):
                    if self.user_info.name is None and result.value.name:
                        self.user_info.name = result.value.name
                    if self.user_info.age is None and result.value.age:
                        self.user_info.age = result.value.age

            except Exception:
                pass  # Failed to extract, continue without updating

    async def invoking(
        self, messages: ChatMessage | MutableSequence[ChatMessage], **kwargs: Any
    ) -> Context:
        """Provide user information context before each agent call."""
        instructions: list[str] = []

        if self.user_info.name is None:
            instructions.append(
                "Ask the user for their name and politely decline to answer any questions until they provide it."
            )
        else:
            instructions.append(f"The user's name is {self.user_info.name}.")

        if self.user_info.age is None:
            instructions.append(
                "Ask the user for their age and politely decline to answer any questions until they provide it."
            )
        else:
            instructions.append(f"The user's age is {self.user_info.age}.")

        # Return context with additional instructions
        return Context(instructions=" ".join(instructions))

    def serialize(self) -> str:
        """Serialize the user info for thread persistence."""
        return self.user_info.model_dump_json()


import asyncio
from agent_framework import ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import AzureCliCredential


async def main():
    async with AzureCliCredential() as credential:
        chat_client = AzureAIAgentClient(
            credential=credential,
            project_endpoint="https://account-400.services.ai.azure.com/api/projects/project-400",  # "https://ai-services-333-400.cognitiveservices.azure.com/",
            model_deployment_name="gpt-4o-mini",
        )

        # Create the memory provider
        memory_provider = UserInfoMemory(chat_client)

        # Create the agent with memory
        async with ChatAgent(
            chat_client=chat_client,
            instructions="You are a friendly assistant. Always address the user by their name.",
            context_providers=memory_provider,
        ) as agent:
            # Create a new thread for the conversation
            thread = agent.get_new_thread()

            print(await agent.run("Hello, what is the square root of 9?", thread=thread))
            print(await agent.run("My name is Ruaidhrí", thread=thread))
            print(await agent.run("I am 20 years old", thread=thread))

            # Access the memory component via the thread's context_providers attribute and inspect the memories
            if thread.context_provider:
                user_info_memory = thread.context_provider.providers[0]
                if isinstance(user_info_memory, UserInfoMemory):
                    print()
                    print(f"MEMORY - User Name: {user_info_memory.user_info.name}")
                    print(f"MEMORY - User Age: {user_info_memory.user_info.age}")


if __name__ == "__main__":
    asyncio.run(main())
