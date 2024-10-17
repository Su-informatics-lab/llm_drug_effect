import pandas as pd
from vllm import LLM, SamplingParams


# hyperparams refer to https://github.com/meta-llama/llama3/blob/main/llama/generation.py
sampling_params = SamplingParams(temperature=0.6, top_p=0.9)
SYSTEM_PROMPT = (
    "You are a medical language model designed to estimate the probability that a patient has "
    "Type II diabetes based on a specific medicine. You may use chain-of-thought reasoning, but "
    "always output your final answer as a float number on a new line starting with 'Estimated Probability:'."
)


def create_conversation(drug):
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
                "You may reason step-by-step, but provide the final answer on a new line in the format: "
                "'Estimated Probability: X', where X is the probability."
            )
        }
    ]


def estimate_diabetes_probability(drugs: list, batch_size: int = 1) -> list:
    """
    Estimate the probability that a patient has Type II diabetes given that they took
    the specified medicines. Use chain-of-thought reasoning and provide the final result
    in a clear float format.

    Args:
        drugs: List of the names of the medicines the patient took.
        batch_size: The number of drugs to process in each batch.

    Returns:
        A list of estimated probabilities between 0 and 1.
    """
    estimated_probabilities = []

    for i in range(0, len(drugs), batch_size):
        batch_drugs = drugs[i:i + batch_size]
        conversations = [create_conversation(drug) for drug in batch_drugs]

        outputs = llm.chat(
            messages=conversations,
            sampling_params=sampling_params,
            use_tqdm=True
        )

        # process in batch
        for output in outputs:
            response_text = output.generations[0].text
            # extract the probability from the model output using the 'Estimated Probability' marker
            lines = response_text.split("\n")
            probability_line = [line for line in lines if "Estimated Probability" in line]

            if probability_line:
                try:
                    # parse the float from the 'Estimated Probability' line
                    estimated_probability = float(probability_line[0].split(":")[1].strip())
                except (IndexError, ValueError):
                    # Handle parsing errors
                    estimated_probability = None
            else:
                estimated_probability = None

            estimated_probabilities.append(estimated_probability)

    return estimated_probabilities


if __name__ == "__main__":

    llm = LLM(model="meta-llama/Meta-Llama-3-8B-Instruct", tensor_parallel_size=2)
    df = pd.read_parquet('drug_15355.parquet', engine='pyarrow')
    drugs = df['values'].tolist()[:100]

    probas = estimate_diabetes_probability(drugs, 1)
    df = pd.DataFrame(probas, columns=['values'])
    df.to_parquet("drug_diabetes_probas.parquet", engine='pyarrow')