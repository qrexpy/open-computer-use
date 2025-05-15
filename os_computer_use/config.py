# Define the models to use in the agent

from os_computer_use import providers
from openai import OpenAI
from os_computer_use.llm_provider import LLMProvider, Message, Text

# Create a ZukiJourney provider class using the OpenAI API structure
class ZukiJourneyProvider(LLMProvider):
    base_url = "https://api.zukijourney.com/v1"
    api_key = "zu-8d81351fe379aa5bc0fd7d66632b0ab4"
    
    def __init__(self, model="gpt-4o"):
        self.model = model
        print(f"Using ZukiJourneyProvider with {self.model}")
        self.client = self.create_client()
    
    def create_client(self):
        return OpenAI(base_url=self.base_url, api_key=self.api_key).chat.completions
    
    def create_function_schema(self, definitions):
        functions = []
        for name, details in definitions.items():
            properties = {}
            required = []
            for param_name, param_desc in details["params"].items():
                properties[param_name] = {"type": "string", "description": param_desc}
                required.append(param_name)
            
            function_def = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": details["description"],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
            functions.append(function_def)
        return functions
    
    def create_image_block(self, image_data):
        import base64
        import io
        from PIL import Image
        
        # Detect image type
        image_type = "png"  # Default
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                image_type = img.format.lower()
        except Exception as e:
            print(f"Error detecting image type: {e}")
        
        # Base64-encode the image
        encoded = base64.b64encode(image_data).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/{image_type};base64,{encoded}"},
        }
    
    def create_tool_call(self, name, parameters):
        return {
            "type": "function",
            "name": name,
            "parameters": parameters,
        }
    
    def wrap_block(self, block):
        if isinstance(block, bytes):
            return self.create_image_block(block)
        else:
            return Text(block)
    
    def transform_message(self, message):
        content = message["content"]
        if isinstance(content, list):
            wrapped_content = [self.wrap_block(block) for block in content]
            return {**message, "content": wrapped_content}
        else:
            return message
    
    def completion(self, messages, **kwargs):
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        new_messages = [self.transform_message(message) for message in messages]
        completion = self.client.create(
            messages=new_messages, model=self.model, **filtered_kwargs
        )
        if hasattr(completion, "error"):
            raise Exception("Error calling model: {}".format(completion.error))
        return completion
    
    def call(self, messages, functions=None):
        import re
        import json
        
        def parse_json(s):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                print(f"Error decoding JSON for tool call arguments: {s}")
                return None
        
        # Ensure messages array has at least one user message
        has_user_message = False
        for msg in messages:
            if msg.get("role") == "user":
                has_user_message = True
                break
        
        # If no user message, add a default one
        if not has_user_message:
            messages.append({"role": "user", "content": "Please help me accomplish my task."})
        
        # Ensure the first message is from user or system
        if messages and messages[0].get("role") not in ["user", "system"]:
            # Insert a system message at the beginning
            messages = [{"role": "system", "content": "You are an AI assistant helping with computer tasks."}, *messages]
        
        # If no messages, add defaults
        if not messages:
            messages = [
                {"role": "system", "content": "You are an AI assistant helping with computer tasks."},
                {"role": "user", "content": "Please help me accomplish my task."}
            ]
        
        # If functions are provided, convert to tools format
        tools = self.create_function_schema(functions) if functions else None
        
        try:
            completion = self.completion(messages, tools=tools)
            message = completion.choices[0].message
        except Exception as e:
            print(f"API Error: {str(e)}")
            # Provide debug info
            print(f"Message structure: {[msg.get('role') for msg in messages]}")
            raise
        
        # Return response text and tool calls separately
        if functions:
            tool_calls = message.tool_calls or []
            combined_tool_calls = [
                self.create_tool_call(
                    tool_call.function.name, parse_json(tool_call.function.arguments)
                )
                for tool_call in tool_calls
                if parse_json(tool_call.function.arguments) is not None
            ]
            
            # Sometimes, function calls are returned unparsed
            if message.content and not tool_calls:
                tool_call_matches = re.search(r"\{.*\}", message.content)
                if tool_call_matches:
                    tool_call = parse_json(tool_call_matches.group(0))
                    parameters = tool_call.get("parameters", tool_call.get("arguments"))
                    if tool_call.get("name") and parameters:
                        combined_tool_calls.append(
                            self.create_tool_call(tool_call.get("name"), parameters)
                        )
                        return None, combined_tool_calls
            
            return message.content, combined_tool_calls
        else:
            return message.content

# Initialize models
grounding_model = providers.OSAtlasProvider()
# grounding_model = providers.ShowUIProvider()

# Create ZukiJourney provider instances for vision and action models
vision_model = ZukiJourneyProvider(model="gpt-4o")
action_model = ZukiJourneyProvider(model="gpt-4o")