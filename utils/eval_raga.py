import os
import json
from utils import load_api_key
from chat_history_extractor import get_user_interaction_data_from_dict, get_user_interaction_data_from_single_user

from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

# Choose the appropriate import based on your API:
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from ragas import SingleTurnSample
from ragas.metrics import AspectCritic
from ragas.metrics import RubricsScore

from datasets import load_dataset
from ragas import EvaluationDataset
from ragas import evaluate

GEMINI_API_KEY = load_api_key("GEMINI_API_KEY")
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

config = {
    "model": "gemini-1.5-pro",  # or other model IDs
    "temperature": 0.4,
    "max_tokens": None,
    "top_p": 0.8,
}

# Initialize with Google AI Studio
evaluator_llm = LangchainLLMWrapper(ChatGoogleGenerativeAI(
    model=config["model"],
    temperature=config["temperature"],
    max_tokens=config["max_tokens"],
    top_p=config["top_p"],
))

# TODO: Google embedding doesn't support Chinese language. Need to translate the chat history first.
evaluator_embeddings = LangchainEmbeddingsWrapper(GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-exp-03-07",  # Google's text embedding model
    #task_type="retrieval_document"  # Optional: specify the task type
))

with open('30_turns_dialogues.json', 'r', encoding='utf-8') as f:
     dialogues = json.load(f)
dialogue_content_string = json.dumps(dialogues, indent=4, ensure_ascii=False) # Format it nicely

rubrics_coherence = {
    "score1": "Responses feel fragmented, with no connection to past interactions.",
    "score2": "Occasional references to history but lack continuity.",
    "score3": "Moderate coherence with some contextual links.",
    "score4": "Consistent use of history to maintain flow.",
    "score5": "Responses feel like a continuous, evolving conversation."
}
scorer_rubrics_coherence = RubricsScore(rubrics=rubrics_coherence, llm=evaluator_llm)

scorer_memory_naturalness = AspectCritic(
    name="memory_naturalness",
    definition="Does the agent incorporate past user information (e.g., preferences, events) into responses in a seamless, human-like manner?",
    llm=evaluator_llm
)

# have removed the ones which are mostly depend on the feelings of users themselves

scorer_memory_completeness = AspectCritic(
    name="Memory Completeness",
    # Use an f-string to easily embed the dialogue content
    definition=f"""Does the agent's response sufficiently cover all relevant aspects of memory? The memory comes from the logs below:
--- MEMORY LOGS START ---
{dialogue_content_string}
--- MEMORY LOGS END ---""",
    llm=evaluator_llm
)

#with open("C:\Users\fengz\PycharmProjects\AI_mate\test\ai_mate\Experiments data\long_term_memory\Unit Test - Complexity\Unit 2\sample_1.json", 'r', encoding='utf-8') as f:
#    raw_data1 = json.load(f)

#with open("C:\Users\fengz\PycharmProjects\AI_mate\test\ai_mate\Experiments data\mem0\Unit Test - Complexity\Unit 2\sample_1.json", 'r', encoding='utf-8') as f:
#    raw_data2 = json.load(f)

with open(r"C:\Users\fengz\PycharmProjects\AI_mate\test\ai_mate\Experiments data\long_term_memory\participant_5.json", 'r', encoding='utf-8') as f:
    raw_data1 = json.load(f)

with open(r"C:\Users\fengz\PycharmProjects\AI_mate\test\ai_mate\Experiments data\mem0\participant_5.json", 'r', encoding='utf-8') as f:
    raw_data2 = json.load(f)


#user_id_to_find = "克里斯"
#user_dataset = get_user_interaction_data_from_dict(user_id_to_find, raw_data)

user_dataset1 = get_user_interaction_data_from_single_user(raw_data1)
print(user_dataset1)
user_dataset2 = get_user_interaction_data_from_single_user(raw_data2)
# TODO: Rubrics based eval needs to be separated, otherwise overwrite each other.
eval_dataset1 = EvaluationDataset.from_dict(user_dataset1)
results1 = evaluate(eval_dataset1, metrics=[scorer_rubrics_coherence, scorer_memory_naturalness, scorer_memory_completeness])
r1_details = results1.to_pandas()
print(f"AI Mate: ", results1)
print(r1_details)


eval_dataset2 = EvaluationDataset.from_dict(user_dataset2)
results2 = evaluate(eval_dataset2, metrics=[scorer_rubrics_coherence, scorer_memory_naturalness, scorer_memory_completeness])
r2_details = results2.to_pandas()
print(f"Mem0: ", results2)
print(r2_details)
