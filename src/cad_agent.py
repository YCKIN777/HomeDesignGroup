import json
import os

class CadAgent:
    def __init__(self, config):
        self.cfg = config
        self.needs_human_review = self.cfg["cad_agent"]["needs_human_review"]

    def run(self, img_path):
        return {
            "source_image": img_path,
            "needs_human_review": self.needs_human_review,
            "room_list": ["客厅","主卧","次卧","厨房","卫生间"],
            "size_data": {"width":12.6, "depth":10.2}
        }
