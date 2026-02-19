import os
import sys
import yaml
from dotenv import load_dotenv

# Ensure we can import from parent directory
sys.path.append(os.getcwd())

try:
    from agents.scripter import Scripter
except ImportError:
    # If running from inside Miskatonic_AI_V2_copy, adjust path
    sys.path.append(os.path.join(os.getcwd(), 'Miskatonic_AI_V2_copy'))
    from agents.scripter import Scripter

# Load environment variables
load_dotenv()

def generate_and_save():
    print("Initializing Scripter...")
    try:
        scripter = Scripter(model_name="gemini-2.0-flash")
    except Exception as e:
        print(f"Error initializing Scripter: {e}")
        return

    theme = "Forbidden library. I want it to be a long script, and a detailed yaml file record the plot, different ending, what items we can get in each room...etc"
    print(f"Generating scenario for theme: '{theme}'...")
    print("(This may take up to 60 seconds for a detailed generation...)")
    
    yaml_content = scripter.generate_campaign(theme)
    
    if "title:" in yaml_content:
        try:
            # Parse YAML to get title for filename
            parsed = yaml.safe_load(yaml_content)
            title = parsed.get('title', 'Generated_Scenario').replace(" ", "_").replace(":", "").replace("'", "")
            
            # Ensure directory exists
            save_dir = "data/campaigns"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                
            filename = f"{save_dir}/{title}.yaml"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            
            print(f"✅ SUCCESS: Scenario saved to '{filename}'")
            print("-" * 40)
            print("Preview of generated content:")
            print(yaml_content[:500] + "...")
            print("-" * 40)
            
        except yaml.YAMLError as e:
            print(f"❌ ERROR: Generated YAML contains syntax errors: {e}")
            print("dumping raw content for inspection:")
            print(yaml_content)
    else:
        print("❌ ERROR: Generation failed or format incorrect (missing 'title').")
        print("Raw Output:")
        print(yaml_content)

if __name__ == "__main__":
    generate_and_save()
