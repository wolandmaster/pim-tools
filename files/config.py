#!/usr/bin/env python3
# Copyright (c) 2022 Sandor Balazsi (sandor.balazsi@gmail.com)

import json

class Config:
    def __init__(self, filename):
        self.filename = filename
        self.config = {}

    def load(self):
        with open(self.filename, 'r') as json_file:
            self.config = json.load(json_file)
        return self

    def save(self):
        with open(self.filename, 'w') as json_file:
            json.dump(self.config, json_file, indent = 2)
        return self

    def has(self, key):
        return key in self.config.keys()

    def get(self, key, default = None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        return self
