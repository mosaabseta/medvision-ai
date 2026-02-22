import torch
import re
from transformers import AutoProcessor, AutoModelForImageTextToText

class MedGemmaEngine:
    def __init__(self, model_id="google/medgemma-4b-it"):
        print(f"🚀 Loading MedGemma checkpoint: {model_id}")

        self.model_id = model_id
        self.processor = AutoProcessor.from_pretrained(model_id)

        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype=torch.bfloat16
        )

        print("✅ MedGemma loaded successfully!")

    def analyze(self, image, prompt="Describe GI findings"):
        """
        Main function used by GI snapshot endpoint.
        
        Returns cleaned output directly.
        """
        formatted_prompt = f"<start_of_image>\n{prompt}"
        inputs = self.processor(
            images=image,
            text=formatted_prompt,
            return_tensors="pt"
        ).to(self.model.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=200,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )

        # Decode output
        output = self.processor.batch_decode(
            output_ids,
            skip_special_tokens=True
        )
        
        print("\n===== MEDGEMMA RAW OUTPUT =====")
        print(output)
        print("================================\n")

        # Extract text from output
        result_text = ""
        
        if isinstance(output, list) and len(output) > 0:
            if isinstance(output[0], str):
                result_text = output[0].strip()
            elif isinstance(output[0], dict) and "generated_text" in output[0]:
                result = output[0]["generated_text"]
                if isinstance(result, list):
                    for msg in reversed(result):
                        if isinstance(msg, dict) and msg.get("role") == "assistant":
                            content = msg.get("content", "")
                            if isinstance(content, list):
                                texts = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
                                result_text = " ".join(texts).strip()
                            else:
                                result_text = str(content).strip()
                            break
                else:
                    result_text = str(result).strip()
        
        if not result_text:
            return "Analysis not available"
        
        # ✅ CLEAN OUTPUT BEFORE RETURNING
        # Remove the prompt that was echoed back
        cleaned = result_text
        
        # Remove the formatted_prompt if it was echoed
        if formatted_prompt in cleaned:
            cleaned = cleaned.replace(formatted_prompt, "").strip()
        
        # Remove common prompt echoes
        prompt_echo_patterns = [
            r"<start_of_image>.*?(?=Finding:|Location:|$)",
            prompt  # Remove the original prompt text
        ]
        
        for pattern in prompt_echo_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        cleaned = cleaned.strip()
        
        print(f"📊 Cleaned output length: {len(cleaned)} chars")
        
        return cleaned if cleaned else "No analysis available"
