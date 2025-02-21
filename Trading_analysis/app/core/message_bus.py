from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, field

@dataclass
class MessageBus:
    subscribers: Dict[str, List[Any]] = field(default_factory=dict)
    messages: List[Tuple[str, Dict, str]] = field(default_factory=list)

    def subscribe(self, agent: Any, topic: str) -> None:
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(agent)

    def publish(self, topic: str, message: Dict, sender: str) -> None:
        self.messages.append((topic, message, sender))
        if topic in self.subscribers:
            for subscriber in self.subscribers[topic]:
                subscriber.receive(topic, message, sender)