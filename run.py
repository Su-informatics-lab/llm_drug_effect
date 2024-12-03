import argparse
import pandas as pd
from vllm import LLM, SamplingParams


SYSTEM_PROMPT = (
    "You are a medical language model designed to estimate the probability that a patient has "
    "Type II diabetes based on a specific medicine. Your goal is to provide the probability as a clear float. "
    "Please keep your reasoning concise and avoid unnecessary explanations. Always output your final answer "
    "as a float number on a new line starting with 'Estimated Probability:'."
)


def create_conversation(drug, cot):
    # generate a conversation template that includes the drug name
    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": (
                f"Given that a patient took {drug}, estimate the probability that they have Type II diabetes. "
                "You may think aloud and reason step-by-step."
                "You should provide the final answer on a new line in the format: "
                "'Estimated Probability: X', where X is the probability."
            ) if cot else
            (
                f"Given that a patient took {drug}, estimate the probability that they have Type II diabetes. "
                "You should provide the final answer on a new line in the format: "
                "'Estimated Probability: X', where X is the probability."
            )
        }
    ]


def estimate_diabetes_probability(drugs: list, cot: bool, batch_size: int = 1) -> list:
    """
    Estimate the probability that a patient has Type II diabetes given that they took
    the specified medicines. Use chain-of-thought reasoning and provide the final result
    in a clear float format.

    Args:
        drugs: List of the names of the medicines the patient took.
        cot: Boolean indicating if chain-of-thought reasoning should be used.
        batch_size: The number of drugs to process in each batch.

    Returns:
        - probas: A list of estimated probabilities between 0 and 1.
        - responses: The raw text responses generated by the model for further analysis.
    """
    estimated_probabilities = []
    response_texts = []

    for i in range(0, len(drugs), batch_size):
        batch_drugs = drugs[i:i + batch_size]
        conversations = [create_conversation(drug, cot) for drug in batch_drugs]

        outputs = llm.chat(
            messages=conversations,
            sampling_params=sampling_params,
            use_tqdm=True
        )

        # process in batch
        for output in outputs:
            response_text = output.outputs[0].text
            response_texts.append(response_text)
            # extract the probability from the model output using the 'Estimated Probability' marker
            lines = response_text.split("\n")
            probability_line = [line for line in lines if
                                "Estimated Probability" in line]

            if probability_line:
                try:
                    # parse the float from the 'Estimated Probability' line
                    estimated_probability = float(
                        probability_line[0].split(":")[1].strip())
                except (IndexError, ValueError):
                    # handle parsing errors
                    estimated_probability = None
            else:
                estimated_probability = None

            estimated_probabilities.append(estimated_probability)

    return estimated_probabilities, response_texts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run diabetes probability estimation with options.")
    parser.add_argument('--model', type=str,
                        default="meta-llama/Meta-Llama-3-8B-Instruct",
                        help='Huggingface model name to use.')
    parser.add_argument('--cot', action='store_true',
                        help='Enable chain-of-thought reasoning.')
    parser.add_argument('--num_gpus', type=int, default=1,
                        help='Number of GPUs to use.')
    parser.add_argument('--temperature', type=float, default=0.6,
                        help='Temperature parameter for sampling.')
    parser.add_argument('--batch_size', type=int, default=4,
                        help='Batch size for estimation.')

    args = parser.parse_args()
    # hyperparams refer to https://github.com/meta-llama/llama3/blob/main/llama/generation.py
    sampling_params = SamplingParams(temperature=args.temperature, top_p=0.9,
                                     max_tokens=1024 * 4)

    llm = LLM(model=args.model,
              tensor_parallel_size=args.num_gpus,
              # dtype='bf16'
              )

    df = pd.read_parquet('drugs_15980.parquet', engine='pyarrow')
    drugs = df['values'].tolist()

    probas, responses = estimate_diabetes_probability(drugs, cot=args.cot,
                                                      batch_size=args.batch_size)
    result_df = pd.DataFrame({
        'prob': probas,
        'response': responses
    })
    save_path = "drug_t2d_15980_probas.parquet" if not args.cot else "drug_t2d_15980_probas_cot.parquet"
    result_df.to_parquet(save_path, engine='pyarrow')
