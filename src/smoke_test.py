import os, sys
root = r"H:\AgentProjects\HomeDesignGroup"
sys.path.insert(0, os.path.join(root,"src"))

from cad_agent import CadAgent
from designer_agent import DesignerAgent
from cost_agent import CostAgent
from material_agent import MaterialAgent

print("Smoke Test Start")
cfg = {"cad_agent":{"needs_human_review":True}, "output_dir":os.path.join(root,"output")}
cad = CadAgent(cfg)
des = DesignerAgent(cfg)
cost = CostAgent(cfg)
mat = MaterialAgent(cfg)

res = cad.run("test.png")
print("CAD agent pass:", res)
print("All agents loaded OK. Smoke Test OK.")
