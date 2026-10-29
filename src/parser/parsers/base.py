"""Базовий клас парсерів: чиста функція «HTML -> модель», без мережі й БД (тестується на фікстурах)."""

from abc import ABC, abstractmethod
from typing import Any


class BaseParser(ABC):
    @abstractmethod
    def parse(self, html: str) -> Any: ...
