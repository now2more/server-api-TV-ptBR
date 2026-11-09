import os
import re

import utils.constants as constants
from utils.tools import get_real_path, resource_path, format_name


class Alias:
    def __init__(self):
        self.reload()

    def reload(self):
"""
[PT-BR]         self.primary_to_aliases: dict[str, set[str]] = {}

[PT-BR]         self.alias_to_primary: dict[str, str] = {}

[PT-BR]         self.pattern_to_primary: list[tuple[re.Pattern, str]] = []



[PT-BR]         real_path = get_real_path(resource_path(constants.alias_path))

[PT-BR]         if os.path.exists(real_path):

[PT-BR]             with open(real_path, "r", encoding="utf-8") as f:

[PT-BR]                 for line in f:

[PT-BR]                     if line.strip() and not line.startswith("#") and "," in line:

[PT-BR]                         parts = [p.strip() for p in line.split(",")]

[PT-BR]                         primary = parts[0]

[PT-BR]                         aliases = set(parts[1:])

[PT-BR]                         aliases.add(format_name(primary))

[PT-BR]                         self.primary_to_aliases[primary] = aliases

[PT-BR]                         for alias in aliases:

[PT-BR]                             self.alias_to_primary[alias] = primary

[PT-BR]                             if alias.startswith("re:"):

[PT-BR]                                 raw_pattern = alias[3:]

[PT-BR]                                 try:

[PT-BR]                                     pattern = re.compile(raw_pattern)

[PT-BR]                                     if (pattern, primary) not in self.pattern_to_primary:

[PT-BR]                                         self.pattern_to_primary.append((pattern, primary))

[PT-BR]                                 except re.error:

[PT-BR]                                     pass

[PT-BR]                         self.alias_to_primary[primary] = primary



[PT-BR]     def get(self, name: str):
"""
        Get the alias by name
        """
        return self.primary_to_aliases.get(name, set())

    def get_primary(self, name: str):
"""
[PT-BR]         Get the primary name by alias
"""
        primary_name = self.alias_to_primary.get(name, None) or self.get_primary_by_pattern(name)
        if primary_name is None:
            alias_format_name = format_name(name)
            primary_name = self.alias_to_primary.get(alias_format_name, name)
        return primary_name

    def get_primary_by_pattern(self, name: str):
"""
[PT-BR]         Get the primary name by pattern match
"""
        for pattern, primary in self.pattern_to_primary:
            if pattern.search(name):
                return primary
        return None

    def set(self, name: str, aliases: set[str]):
"""
[PT-BR]         Set the aliases by name
"""
        if name in self.primary_to_aliases:
            for alias in self.primary_to_aliases[name]:
                self.alias_to_primary.pop(alias, None)
        self.primary_to_aliases[name] = set(aliases)
        for alias in aliases:
            self.alias_to_primary[alias] = name
            if alias.startswith("re:"):
                raw_pattern = alias[3:]
                try:
                    pattern = re.compile(raw_pattern)
                    if (pattern, name) not in self.pattern_to_primary:
                        self.pattern_to_primary.append((pattern, name))
                except re.error:
                    pass
        self.alias_to_primary[name] = name
