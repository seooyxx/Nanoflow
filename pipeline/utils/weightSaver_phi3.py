import safetensors
import sys
sys.path.append('../build')
import torch
import os
import tqdm
import json
import argparse
import torch

os.environ['HF_HOME'] = '../../../hf'
from transformers import AutoModelForCausalLM, AutoTokenizer, LlamaModel, LlamaForCausalLM



weightDir = ""

# Create the directory if it does not exist
# if not os.path.exists(weightDir):
#     os.makedirs(weightDir)

def tensorop_process(tensor, split_direction, major, vnranks):
    result_list = []
    if split_direction == 'K':
        result_list = tensor.split(tensor.size()[1] // vnranks, 1)
    elif split_direction == 'N':
        result_list = tensor.split(tensor.size()[0] // vnranks, 0)
    else:
        result_list = [tensor] * vnranks
    
    result_list = list(result_list)
    
    if major == 'Row':
        for i in range(vnranks):
            result_list[i] = result_list[i].t().contiguous()
    elif major == 'Col':
        pass
        
    
    return result_list

def load_tensors(tensor_path):
    
    original_tensors ={}
    for file in tqdm.tqdm(os.listdir(tensor_path)):
        if file.endswith(".safetensors"):
            tensors = safetensors.safe_open(os.path.join(tensor_path, file), 'pt')
            for name in tensors.keys():
                tensor = tensors.get_tensor(name)
                original_tensors[name] = tensor
    return original_tensors


# name_map={
#     "ln_attention":    "model.layers.{i}.input_layernorm.weight",
#     "w_d":    "model.layers.{i}.mlp.down_proj.weight",
#     "w_g":    "model.layers.{i}.mlp.gate_proj.weight",
#     "w_u":    "model.layers.{i}.mlp.up_proj.weight",
#     "ln_ffn":    "model.layers.{i}.post_attention_layernorm.weight",
#     "w_k":    "model.layers.{i}.self_attn.k_proj.weight",
#     "w_o":    "model.layers.{i}.self_attn.o_proj.weight",
#     "w_q":    "model.layers.{i}.self_attn.q_proj.weight",
#     "w_rot":    "model.layers.{i}.self_attn.rotary_emb.inv_freq",
#     "w_v":    "model.layers.{i}.self_attn.v_proj.weight",
#     "b_k":    "model.layers.{i}.self_attn.k_proj.bias",
#     "b_q":    "model.layers.{i}.self_attn.q_proj.bias",
#     "b_v":    "model.layers.{i}.self_attn.v_proj.bias"
# }

name_map={
    "ln_attention":    "model.layers.{i}.input_layernorm.weight",
    "w_d":    "model.layers.{i}.mlp.down_proj.weight",
    "w_g":    "model.layers.{i}.mlp.gate_proj.weight",
    "w_u":    "model.layers.{i}.mlp.up_proj.weight",
    "ln_ffn":    "model.layers.{i}.post_attention_layernorm.weight",
    "w_o":    "model.layers.{i}.self_attn.o_proj.weight",
    "w_qkv":    "model.layers.{i}.self_attn.qkv_proj.weight",
}

tensor_save_list = []

        
def save_weights( nranks, vnranks, weightDir, model_path = '/code/hf/hub/models--meta-llama--Llama-2-70b-chat-hf/snapshots/e9149a12809580e8602995856f8098ce973d1080/'):
    tensor_saved = []
    model_weights = []
    
    if not os.path.exists(weightDir):
        os.makedirs(weightDir)
    
    # load config file of hub model
    huggingface_config = json.load(open(os.path.join(model_path, 'config.json')))
    num_layers = huggingface_config['num_hidden_layers']
    print(f"Number of layers: {num_layers}")

    original_tensors = load_tensors(model_path)
    for key in original_tensors.keys():
        print(key, original_tensors[key].shape)
    
    model_norms = tensorop_process(original_tensors['model.norm.weight'], 'C', 'Row', vnranks)
    lm_heads = tensorop_process(original_tensors['lm_head.weight'], 'C', 'Row', vnranks)
    embeds = tensorop_process(original_tensors['model.embed_tokens.weight'], 'C', 'Col', vnranks)
    dict_weights = []
    for i in range(nranks):
        dict_weights.append({
            "ModelNorm": model_norms[i],
            "Embed": embeds[i],
            "LmHead": lm_heads[i]
        })
        
    for l in tqdm.tqdm(range(num_layers)):
        w_o1 = tensorop_process(original_tensors[name_map['w_o'].format(i=l)], 'N', 'Row', vnranks)
        w_o2 = tensorop_process(original_tensors[name_map['w_o'].format(i=l)], 'K', 'Row', vnranks)
        # original_ug = torch.cat([original_tensors[name_map['w_u'].format(i=l)], original_tensors[name_map['w_g'].format(i=l)]], 0)
        w_u = tensorop_process(original_tensors[name_map['w_u'].format(i=l)], 'N', 'Row', vnranks)
        w_g = tensorop_process(original_tensors[name_map['w_g'].format(i=l)], 'N', 'Row', vnranks)
        # w_ug = []
        # for i in range(nranks):
        #     w_ug.append(torch.cat([w_u[i], w_g[i]], 1))
        
        w_d = tensorop_process(original_tensors[name_map['w_d'].format(i=l)], 'K', 'Row', vnranks)
        w_kqv = tensorop_process(original_tensors[name_map['w_qkv'].format(i=l)], 'N', 'Row', vnranks)

        # u_k = tensorop_process(original_tensors[name_map['w_k'].format(i=l)], 'N', 'Row', vnranks)
        # u_q = tensorop_process(original_tensors[name_map['w_q'].format(i=l)], 'N', 'Row', vnranks)
        # u_v = tensorop_process(original_tensors[name_map['w_v'].format(i=l)], 'N', 'Row', vnranks)
        # print(u_k[0].shape, u_q[0].shape, u_v[0].shape)
        # for i in range(nranks):
        #     w_kqv.append(torch.cat([u_k[i], u_v[i], u_q[i]], 1))
        # print(w_kqv[0].shape)
        
        # b_kqv = []
        # if name_map['b_k'].format(i=l) in original_tensors:
        #     b_k = tensorop_process(original_tensors[name_map['b_k'].format(i=l)], 'N', 'Row', vnranks)
        #     b_q = tensorop_process(original_tensors[name_map['b_q'].format(i=l)], 'N', 'Row', vnranks)
        #     b_v = tensorop_process(original_tensors[name_map['b_v'].format(i=l)], 'N', 'Row', vnranks)
        #     for i in range(nranks):
        #         b_kqv.append(torch.cat([b_k[i].unsqueeze(0), b_v[i].unsqueeze(0), b_q[i].unsqueeze(0)], 1))
        # else:
        #     for i in range(nranks):
        #         b_kqv.append(torch.zeros(1, u_k[0].shape[1]+u_v[0].shape[1]+u_q[0].shape[1]))

        w_ln_attention = tensorop_process(original_tensors[name_map['ln_attention'].format(i=l)], 'C', 'Row', vnranks)
        w_ln_ffn = tensorop_process(original_tensors[name_map['ln_ffn'].format(i=l)], 'C', 'Row', vnranks)

        for i in range(nranks):
            dict_weights[i].update({
                f"O1_{l}": w_o1[i].to(torch.float16),
                f"O2_{l}": w_o2[i].to(torch.float16),
                # f"UG_{l}": w_ug[i],
                f"U_{l}": w_u[i].to(torch.float16),
                f"G_{l}": w_g[i].to(torch.float16),
                f"D_{l}": w_d[i].to(torch.float16),
                f"KQV_{l}": w_kqv[i].to(torch.float16),
                # f"BKQV_{l}": b_kqv[i].to(torch.float16),
                f"LNATT_{l}": w_ln_attention[i].to(torch.float16),
                f"LNFFN_{l}": w_ln_ffn[i].to(torch.float16)
            })
    for i in range(nranks):
        torch.save(dict_weights[i], os.path.join(weightDir, f"weight_rank_{i}.pt"))

def download_weights(model_name):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
 
if __name__ == "__main__":

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--config_path", type=str, default="../config_all/llama2-70B/2048.json", help="Model config JSON file to read from")

    args = arg_parser.parse_args()
    
    with open(args.config_path, 'r') as file: 
        nanoflow_config = json.load(file)
    model_name = nanoflow_config["serve_configs"]["model"]
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    
    model_path = nanoflow_config["serve_configs"]["hf_path"]
    weightDir = nanoflow_config["serve_configs"]["weight_path"]

    save_weights(nanoflow_config["serve_configs"]["actual_gpu_num"],
                 nanoflow_config["model_configs"]["gpu_num"], 
                 weightDir=weightDir,
                 model_path=model_path)

