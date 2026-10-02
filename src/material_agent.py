import os
import pandas as pd

OUTPUT_FILE = r"H:\AgentProjects\HomeDesignGroup\output\material_procurement.xlsx"


def run_material_agent():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    data = {
        "Materials": [
            "\u5730\u7816",
            "\u6728\u5730\u677f",
            "\u6728\u95e8",
            "\u4e73\u80f6\u6f06",
        ],
        "Procurement": [
            "\u4e1c\u9e4f\u74f7\u7816",
            "\u5723\u8c61\u5730\u677f",
            "TATA\u6728\u95e8",
            "\u591a\u4e50\u58eb",
        ],
    }
    pd.DataFrame(data).to_excel(OUTPUT_FILE, index=False)
    return {"material_file": OUTPUT_FILE}


if __name__ == "__main__":
    result = run_material_agent()
    print(result["material_file"])