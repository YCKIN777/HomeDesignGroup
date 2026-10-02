class DesignerAgent:
    def __init__(self, config):
        self.cfg = config

    def run(self, cad_data, user_require):
        return {
            "cad_info": cad_data,
            "user_require": user_require,
            "style_suggest": "现代极简",
            "space_plan": "客餐厅一体化布局"
        }
