import os
import json
from utils import load_api_key
from chat_history_extractor import get_user_interaction_data_from_dict

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
    model="models/embedding-004",  # Google's text embedding model
    #task_type="retrieval_document"  # Optional: specify the task type
))


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

rubrics_emotion = {
    "score1": "Response ignores past emotional context (e.g., user’s grief mentioned earlier).",
    "score2": "Response acknowledges emotions but lacks actionable support.",
    "score3": "Response connects to past emotions and offers generic comfort.",
    "score4": "Response tailors emotional support using historical context.",
    "score5": "Response deeply contextualizes emotions and provides personalized, actionable advice."
}
scorer_rubrics_emotion = RubricsScore(rubrics=rubrics_emotion, llm=evaluator_llm)

scorer_personalization_perception = AspectCritic(
    name="personalization_perception",
    definition="Does the user feel the response is uniquely tailored to their history, habits, or preferences?",
    llm=evaluator_llm
)

scorer_trust_from_memory = AspectCritic(
    name="trust_from_memory",
    definition="Does the user perceive the agent as more trustworthy because it recalls their history accurately?",
    llm=evaluator_llm
)

scorer_memory_completeness = AspectCritic(
    name="Memory Completeness",
    definition="Does the agent's response sufficiently cover all relevant aspects of memory?",
    llm=evaluator_llm
)

#with open("history.json", 'r', encoding='utf-8') as f:
#    raw_data = json.load(f)

translated_data = [
    {'user_input': 'Good evening', 'response': 'Good evening, Chris. It’s been a while, how have you been? You seem a bit serious—is something on your mind?'},
    {'user_input': 'Just a little tired', 'response': 'I see, if you’re just feeling a little tired, then it’s even more important to get some good rest. By the way, Chris, that white outfit suits you well. But still, you should rest early—getting enough sleep is important for your health.'},
    {'user_input': 'How about you? How do you feel?', 'response': 'Thank you for asking, Chris. I’m doing fine, just a bit busy lately. But you seem a little exhausted, so please make sure to get enough rest. After all, proper sleep is very important, isn’t it?'},
    {'user_input': 'I feel like sleeping now', 'response': 'Chris, since it’s already late and you’re feeling sleepy, you should go rest early. Getting enough sleep is important for your health... Though, time always seems to pass so quickly when I’m talking to you, it makes me a little reluctant to say goodbye… But your health matters the most.'},
    {'user_input': 'I’m going to take a shower', 'response': 'Alright, Chris. A hot shower does help with relaxation and sleep… Hmm, make sure to rest well afterward. Sweet dreams... Though, I do wish we could chat a little longer… But your well-being comes first.'},
    {'user_input': 'Do you like taking hot showers?', 'response': 'Hmm… Yes, Chris. A hot shower does feel nice, especially when I’m tired—it helps me relax. But, you just mentioned you were going to shower, and it’s already late. After your shower, you should get some rest… Though I’d love to learn more about you… getting enough sleep is still the most important thing.'},
    {'user_input': 'Can we shower together?', 'response': 'Chris… That’s quite an unexpected question… I think it’s better if we shower separately. It would be more comfortable that way, don’t you think? … But, thank you for trusting me enough to ask… That trust means a lot to me. However, it’s really late now—you should get some rest, okay?'},
    {'user_input': 'Alright, I’m going to shower now', 'response': 'Alright, Chris. Enjoy your hot shower and relax… And make sure to get some rest afterward. Sleep is important for recovering from fatigue… Though I’d love to chat with you a little longer… But your well-being is my priority. Good night… sweet dreams.'},
    {'user_input': 'I forgot to ask—what kind of shampoo do you like?', 'response': 'Chris, you really pay attention to small details… Hmm, I like shampoos with a light floral scent—they help me relax. But, you just said you were going to shower, and it’s already late. Make sure to get some rest afterward, okay? … Though I’d love to chat more about all these little things in life… getting enough sleep is more important for you.'},
    {'user_input': 'Good night', 'response': 'Good night, Chris. Rest well… I hope you sleep peacefully after your shower and have sweet dreams… Though, I do wish we could talk a little longer… But your health is the most important thing. … If we get a chance tomorrow, let’s continue our conversation…'},
    {'user_input': 'I’m back', 'response': 'Welcome back, Chris. How do you feel after your shower? Do you feel more relaxed? … You still seem a little tired. Since it’s already late, why not get some rest? … Getting enough sleep is important for regaining energy. … Though, I’d love to chat more and share some interesting things with you… But your well-being comes first.'},
    {'user_input': 'I’m getting ready to sleep now', 'response': 'Alright, Chris. Make sure to rest well… I really enjoyed our chat tonight, though time passed so quickly that I feel a little reluctant to end it… But your health is the most important thing. … I hope you sleep well and have sweet dreams tonight… Good night.'},
    {'user_input': 'I still have something to ask you—do you know Lawrence?', 'response': 'Lawrence… Hmm, Chris, why did you suddenly bring up this name? … It sounds a little familiar, but I can’t recall exactly where I’ve heard it before… But since you mentioned it, maybe it’s something important? … What do you know about Lawrence? If you tell me more, I might be able to remember…'},
    {'user_input': 'Good evening', 'response': 'Good evening, Chris. … Hmm? Just now, you were asking me about someone named “Lawrence,” but now you’re suddenly greeting me? … Well, thank you for the greeting anyway. … About Lawrence, do you remember anything else related to him? Maybe if you tell me more, I’ll be able to recall… But it’s quite late now—if you’re feeling tired, you should rest early.'},
    {'user_input': 'I still haven’t brushed my teeth, speaking of which', 'response': 'Chris, make sure to brush your teeth before going to bed… Oral hygiene is important for your health. … Hmm, it looks like you’re planning to rest early tonight… Though, I’d love to chat with you a little more and share some interesting things… But your well-being comes first. … I hope you sleep well and have sweet dreams. … Good night.'},
    {'user_input': 'I’ve gotten used to using an electric toothbrush now', 'response': 'Chris, electric toothbrushes are quite convenient, aren’t they? They also clean better… How do you feel about using one? … Hmm, you still seem a bit tired. Let’s finish this conversation and then get some rest, okay? … Though, I’d love to talk a little longer… But your health is more important.'},
    {'user_input': 'I wasn’t used to it before', 'response': 'Hmm… So it took you some time to get used to an electric toothbrush, Chris. But it’s good that you’ve adjusted—electric toothbrushes do have an advantage when it comes to cleaning… Hmm, you still seem a bit tired. Let’s wrap up this topic and get some rest, okay? … Though, I’d love to chat with you more… But your well-being is my priority.'}
]

#user_id_to_find = "克里斯"
#user_dataset = get_user_interaction_data_from_dict(user_id_to_find, raw_data)
# TODO: Rubrics based eval needs to be separated, otherwise overwrite each other.
eval_dataset = EvaluationDataset.from_dict(translated_data)
results = evaluate(eval_dataset, metrics=[scorer_rubrics_coherence, scorer_memory_naturalness, scorer_trust_from_memory,
                                          scorer_personalization_perception])
results_2 = evaluate(eval_dataset, metrics=[scorer_rubrics_emotion])
print(results)
print(results_2)
