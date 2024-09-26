current_dir=$(pwd)
parentdir="$(dirname "$current_dir")"
mkdir -p $parentdir/hf

export HF_HOME=$parentdir/hf
HF_HOME=$parentdir/hf
#check if token is cached
if [ ! -f $HF_HOME/token ]; then
    echo "Please login to Hugging Face to cache your token."
    huggingface-cli login
fi


cd pipeline/utils
read -e -p "Prompt [default: The University of Washington is located]: " -i "The University of Washington is located" prompt
read -e -p "Decode length [default: 100]: " -i "100" decode_length
read -e -p "Output file [default: trace.csv]: " -i "trace.csv" output_file

# Prompt for model selection and map the selection to a specific model path
echo "Selected model: Phi-3-medium-4k-instruct "

config_path=../config_all/phi3-14B/local.json

python gen_req.py "${prompt}" ${decode_length} 0 ${output_file}

python serve_phi3.py -t ${output_file} -c ${config_path} -r 200
output_file_base="${output_file%.csv}"
cat ${output_file_base}.req_words