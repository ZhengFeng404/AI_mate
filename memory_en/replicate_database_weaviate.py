import weaviate
import weaviate.classes as wvc
import weaviate.classes.config as wc
from weaviate.classes.config import Property, DataType, Configure
import os
import json
import shutil

client = weaviate.connect_to_local(port=8081,
    grpc_port=50052,) # for the experiment database setting

# Check if the Collection already exists, and delete it if it does (convenient for example running, handle as needed in actual applications)
collection_names = ["Events", "Relationships", "Knowledge", "Goals", "Preferences", "Profile"]
for collection_name in collection_names:
    if client.collections.exists(collection_name):
        client.collections.delete(collection_name)

print("Old Class (if any) has been deleted")

# 1. Define Events Collection
client.collections.create(
    name="Events",
    description="Stores events experienced by an individual",
    properties=[
        Property(
            name="individual",
            data_type=DataType.TEXT,
            description="The main person involved in the event"
        ),
        Property(
            name="description",
            data_type=DataType.TEXT,
            description="Textual description of the event"
        ),
        Property(
            name="date",
            data_type=DataType.DATE,
            description="Time the event occurred",
            indexRangeFilters=True
        ),
        Property(
            name="duration",
            data_type=DataType.NUMBER,
            description="Duration of the event (e.g., minutes, hours)",
            indexRangeFilters=True
        ),
        Property(
            name="location",
            data_type=DataType.TEXT,
            description="Location where the event occurred"
        ),
        # Adding geo coordinates is an interesting idea but needs more consideration and better design
        #Property(name="geoLocation",data_type=DataType.GEO_COORDINATES,description="事件发生的地点的经纬度"),
        Property(
            name="locationDetails",
            data_type=DataType.TEXT,
            description="More detailed location description (e.g., which area of the park, seat in the cafe, sofa in the living room at home)"
        ),
        Property(
            name="participants",
            data_type=DataType.TEXT_ARRAY,
            description="Participants in the event"
        ),
        Property(
            name="emotionalTone",
            data_type=DataType.TEXT,
            description="Emotional tone of the event (e.g., happy, sad, excited)"
        ),
        Property(
            name="keyMoments",
            data_type=DataType.TEXT,
            description="Key details of the event"
        ),
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Events Collection Schema created successfully")
client.close()

# 2. Define Relationships Collection
client.connect()
client.collections.create(
    name="Relationships",
    description="Stores the relationships of an individual with other people or entities",
    properties=[
        Property(name="subjectName", data_type=DataType.TEXT,
                            description="Name of the relationship subject or entity name"),
        Property(name="relationshipDescription", data_type=DataType.TEXT, description="Description of the relationship"),
        Property(name="objectName", data_type=DataType.TEXT,
                            description="Name of the related person or entity name"),
        Property(name="relationshipType", data_type=DataType.TEXT,
                            description="Type of relationship (e.g., friend, family, romantic, employment, colleague, idol)"),
        Property(name="sentiment", data_type=DataType.TEXT,
                            description="Emotional tendency towards the relationship object (e.g., like, trust, dependence, dislike, jealousy)"),
        Property(name="sentimentStrength", data_type=DataType.NUMBER,
                            description="Strength of the relationship's emotional tendency (e.g., range 0-1)"),
        Property(name="relationshipStage", data_type=DataType.TEXT,
                            description="Stage of the relationship (e.g., initial acquaintance, familiar, stable, indifferent, broken down)"),
        Property(
            name="lastInteractionDate",
            data_type=DataType.DATE,
            description="Time of the most recent interaction",
            indexRangeFilters=True
        ),
        Property(
            name="relationshipCreationTime",
            data_type=DataType.DATE,
            description="Time when this relationship was recorded in the memory bank",
        )
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Relationships Collection Schema created successfully")
client.close()

# 3. Define Knowledge Collection
client.connect()
client.collections.create(
    name="Knowledge",
    description="Stores knowledge, facts, skills, etc., learned by the virtual persona",
    properties=[
        Property(
            name="title",
            data_type=DataType.TEXT,
            description="Title or name of the knowledge entry"
        ),
        Property(
            name="content",
            data_type=DataType.TEXT,
            description="Detailed content of the knowledge entry"
        ),
        Property(
            name="category",
            data_type=DataType.TEXT,
            description="Category the knowledge belongs to (e.g., games, anime, medicine, law)"
        ),
        Property(
            name="source",
            data_type=DataType.TEXT,
            description="Source of the knowledge (e.g., books, websites, conversations)"
        ),
        Property(
            name="keywords",
            data_type=DataType.TEXT_ARRAY,
            description="A list of keywords")
        ,
        Property(
            name="relevanceScore",
            data_type=DataType.NUMBER,
            description="Relevance score of the knowledge entry"
        ),
        Property(
            name="confidenceLevel",
            data_type=DataType.NUMBER,
            description="Confidence level in the knowledge (e.g., range 0-1, the reliability of the knowledge's authenticity)"
        ),
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Knowledge Collection Schema created successfully")
client.close()

# 4. Define Goals Collection
client.connect()
client.collections.create(
    name="Goals",
    description="Used to store an individual's goals, plans, wishes, or decisions",
    properties=[
        Property(
            name="owner",
            data_type=DataType.TEXT,
            description="The owner of this goal"
        ),
        Property(
            name="goalDescription",
            data_type=DataType.TEXT,
            description="Description of the goal"
        ),
        Property(
            name="goalType",
            data_type=DataType.TEXT,
            description="Type of goal"
        ),
        Property(
            name="motivation",
            data_type=DataType.TEXT,
            description="Motivation and reasons for the goal"
        ),
        Property(
            name="status",
            data_type=DataType.TEXT,
            description="Status of goal achievement (e.g., planning, in progress, completed, abandoned)"
        ),
        Property(
            name="progress",
            data_type=DataType.NUMBER,
            description="Progress of goal completion (e.g., range 0-1, or percentage)"
        ),
        Property(
            name="obstacles",
            data_type=DataType.TEXT_ARRAY,
            description="Obstacles and challenges encountered in the process of achieving the goal"
        ),
        Property(
            name="startingDate",
            data_type=DataType.DATE,
            description="Date the goal was set",
            indexRangeFilters=True

        ),
        Property(
            name="endingDate",
            data_type=DataType.DATE,
            description="Date the goal is expected to end"
        ),
        Property(
            name="priority",
            data_type=DataType.TEXT,
            description="Priority of the goal (e.g., high, medium, low)"
        ),
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Goals Collection Schema created successfully")
client.close()

# 5. Define Preferences Collection
client.connect()
client.collections.create(
    name="Preferences",
    description="Stores an individual's preferences, likes, values, etc.",
    properties=[
        Property(
            name="preferenceOwner",
            data_type=DataType.TEXT,
            description="Owner of the preference"
        ),
        Property(
            name="preferenceType",
            data_type=DataType.TEXT,
            description="Type of preference (e.g., food preference, music preference, color preference, values, morals)"
        ),
        Property(
            name="preferenceDescription",
            data_type=DataType.TEXT,
            description="Description of the preference"
        ),
        Property(
            name="reasoning",
            data_type=DataType.TEXT,
            description="Reasons or logic behind the preference"
        ),
        Property(
            name="preferenceStrength",
            data_type=DataType.TEXT,
            description="Divided into five levels of strength (Slight 1, Somewhat 2, Moderate 3, Especially 4, Strong 5)"
        ),
        Property(
            name="confidenceLevel",
            data_type=DataType.NUMBER,
            description="Confidence level of the preference (e.g., range 0-1)"
        ),
        Property(
            name="preferenceCreationTime",
            data_type=DataType.DATE,
            description="Time when this preference was recorded in the memory bank"
        ),
    ],
    vectorizer_config=
        Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            # If using Docker, use this to contact your local Ollama instance
            model="mxbai-embed-large:latest",
        ),
)

print("Preferences Collection Schema created successfully")

client.connect()
client.collections.create(
    name="Profile",
    description="Stores an individual's long-term identity information, including basic information, health status, social identity, economic status, living situation, etc.",
    properties=[
        # Basic Information
        Property(name="fullName", data_type=DataType.TEXT, description="Full name"),
        Property(name="nickname", data_type=DataType.TEXT, description="Common nickname"),
        Property(name="dateOfBirth", data_type=DataType.DATE, description="Date of birth"),
        Property(name="age", data_type=DataType.NUMBER, description="Age"),
        Property(name="gender", data_type=DataType.TEXT, description="Gender"),
        Property(name="height", data_type=DataType.NUMBER, description="Height (cm)"),
        Property(name="weight", data_type=DataType.NUMBER, description="Weight (kg)"),

        # Health Status
        Property(name="chronicDiseases", data_type=DataType.TEXT_ARRAY, description="Chronic diseases (e.g., diabetes, asthma, etc.)"),
        Property(name="disabilities", data_type=DataType.TEXT_ARRAY, description="Physical disabilities or special health conditions"),
        Property(name="allergies", data_type=DataType.TEXT_ARRAY, description="Allergens (e.g., pollen, seafood, etc.)"),
        Property(name="bloodType", data_type=DataType.TEXT, description="Blood type"),
        Property(name="medicalHistory", data_type=DataType.TEXT, description="Past major illnesses or surgery records"),

        # Social Identity
        Property(name="educationLevel", data_type=DataType.TEXT, description="Education level (e.g., primary school, university, postgraduate, etc.)"),
        Property(name="schoolOrUniversity", data_type=DataType.TEXT, description="Current or past school attended"),
        Property(name="jobTitle", data_type=DataType.TEXT, description="Job title"),
        Property(name="companyOrEmployer", data_type=DataType.TEXT, description="Work unit"),
        Property(name="jobLevel", data_type=DataType.TEXT,
                 description="Job level (e.g., intern, manager, senior engineer, associate professor, etc.)"),
        Property(name="socialRole", data_type=DataType.TEXT, description="Social role (e.g., student, teacher, doctor, artist)"),

        # Economic Status
        Property(name="incomeLevel", data_type=DataType.TEXT, description="Income level (low income, middle income, high income)"),
        Property(name="financialDebts", data_type=DataType.TEXT, description="Financial debts"),

        # Living Situation
        Property(name="currentResidence", data_type=DataType.TEXT, description="Current place of residence (city, country)"),
        Property(name="hometown", data_type=DataType.TEXT, description="Hometown (place of birth)"),
        Property(name="livingWith", data_type=DataType.TEXT, description="Living with whom (living alone, with family, with roommates)"),
        Property(name="housingType", data_type=DataType.TEXT, description="Housing type (apartment, detached house, dormitory, etc.)"),

        # Cultural Background
        Property(name="nationality", data_type=DataType.TEXT, description="Nationality"),
        Property(name="ethnicity", data_type=DataType.TEXT, description="Ethnicity"),
        Property(name="religion", data_type=DataType.TEXT, description="Religious beliefs"),

        # Update Time
        Property(name="profileLastUpdated", data_type=DataType.DATE, description="Last updated time of this profile"),
    ],
    vectorizer_config=
    Configure.Vectorizer.text2vec_ollama(
        api_endpoint="http://host.docker.internal:11434",
        model="mxbai-embed-large:latest",
    ),
)
print("Profile Collection Schema created successfully")

print("All Collection Schemas defined!")

file_path = "30_turns_memory_entries.json"

try:
    with open(file_path, 'r', encoding='utf-8') as f:  # Specify using utf-8 encoding
        loaded_memory_entries_json = json.load(f)
    print("Successfully loaded JSON data from file.")

    for entry in loaded_memory_entries_json:  # Use the parsed JSON data
        if isinstance(entry, dict):  # Ensure entry is a dictionary
            if "class" in entry:  # Check if the "class" key exists
                class_name = entry["class"]
                collection = client.collections.get(class_name)
                # ... your other code ...
                print(f"Processing class name: {class_name}") # Example output
                if "properties_content" in entry:
                    properties_content = entry["properties_content"]
                    print(f"Properties content: {properties_content}") # Example output
                if "action" in entry:
                    action = entry["action"]
                    print(f"Action: {action}") # Example output
                    if action == "UPDATE":
                        if "updated_object_id" in entry:
                            uuid = entry["updated_object_id"]
                            print(f"Updated UUID: {uuid}") # Example output
                            collection.data.update(uuid=uuid, properties=properties_content)
                        else:
                            print("Warning: 'UPDATE' action is missing 'updated_object_id'")
                    elif action == "ADD":
                        collection.data.insert(properties_content)
                        print("Performing add operation") # Example output
                    else:
                        print(f"Unknown action: {action}")
                else:
                    print("Warning: Missing 'action' key")
            else:
                print("Warning: JSON entry is missing 'class' key")
        else:
            print("Warning: JSON entry is not a dictionary")

except FileNotFoundError:
    print(f"Error: File {file_path} not found.")
except json.JSONDecodeError as e:
    print(f"Error: An error occurred while parsing the JSON file: {e}")
except Exception as e:
    print(f"An error occurred while reading and processing the JSON file: {e}")