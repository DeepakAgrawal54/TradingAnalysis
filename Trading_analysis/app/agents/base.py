# app/agents/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any
from core.message_bus import MessageBus
from langchain_openai import ChatOpenAI

class FinancialAgent(ABC):
    def __init__(self, name: str, role: str, bus: MessageBus, llm: ChatOpenAI):
        self.name = name
        self.role = role
        self.bus = bus
        self.llm = llm

    def send(self, topic: str, message: Dict[str, Any]) -> None:
        self.bus.publish(topic, message, self.name)

    def receive(self, topic: str, message: Dict[str, Any], sender: str) -> None:
        if self.should_handle(topic, message):
            try:
                self.process_message(topic, message, sender)
            except Exception as e:
                print(f"❌ {self.name} error while processing {topic}: {str(e)}")

    @abstractmethod
    def should_handle(self, topic: str, message: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def process_message(self, topic: str, message: Dict[str, Any], sender: str) -> None:
        pass