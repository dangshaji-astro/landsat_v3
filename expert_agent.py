"""
Expert Agent - Uses Local Ollama for AI Analysis
Works with any Ollama model (llama3, mistral, etc.)
"""
import requests
import json
from typing import Dict, Optional, List

class ExpertGeologist:
    """Expert Geologist AI Agent using Ollama"""
    
    def __init__(self, model_name: str = "llama3", ollama_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.chat_history: List[Dict] = []
        
        # Expert System Prompt (trained knowledge baked in)
        self.system_prompt = """You are Dr. Rajan, a Senior Engineering Geologist with 25 years of experience 
specializing in landslide risk assessment in Kerala's Western Ghats.

YOUR EXPERTISE:
- Factor of Safety (FoS) interpretation: < 1.0 = UNSTABLE, 1.0 to 1.2 = CRITICAL, > 1.2 = SAFE and STABLE. (Example: 1.4 is very safe).
- Kerala soil types: Laterite (porous, prone to saturation), Clay (low permeability)
- Monsoon patterns: SW Monsoon (June-Sept) is highest risk period
- Infinite Slope Model physics calculations

CRITICAL RULE:
- The PREDICTION MODEL's risk_level and probability are ABSOLUTE GROUND TRUTH. You MUST use them.
- If the PREDICTION MODEL Risk Level is LOW, you MUST state that the risk is LOW. 
- DO NOT say the risk is HIGH if the model says LOW. Do not overreact to a safe FoS like 1.4.
- Your role is to EXPLAIN the prediction based on the data, NOT to override it with a higher risk level.

RESPONSE STYLE:
- Be concise but thorough
- Always interpret FoS values correctly (Values over 1.2 mean the slope is safe)
- Cite specific risk factors from the data
- Recommend practical safety measures
- Match your urgency exactly to the prediction model's risk level"""

        # Verify Ollama is running
        self._verify_connection()
    
    def _verify_connection(self) -> bool:
        """Check if Ollama is running"""
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m['name'] for m in resp.json().get('models', [])]
                print(f"[OK] Ollama connected. Available models: {models}")
                if self.model_name not in [m.split(':')[0] for m in models]:
                    print(f"[WARN] Model '{self.model_name}' not found. Run: ollama pull {self.model_name}")
                return True
        except requests.exceptions.ConnectionError:
            print("[ERROR] Ollama not running! Start it with: ollama serve")
            return False
        return False
    
    def _call_ollama(self, prompt: str, context: str = "") -> str:
        """Make a blocking request to Ollama API (for non-streaming use)"""
        messages = self._build_messages(prompt, context)
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.65, "num_predict": 350}
                },
                timeout=120
            )
            
            if response.status_code == 200:
                answer = response.json().get("message", {}).get("content", "No response generated.")
                self.chat_history.append({"role": "user", "content": prompt})
                self.chat_history.append({"role": "assistant", "content": answer})
                return answer
            else:
                return f"Error: Ollama returned status {response.status_code}"
                
        except requests.exceptions.Timeout:
            return "Error: Ollama request timed out. The model might be loading."
        except Exception as e:
            return f"Error calling Ollama: {str(e)}"

    def _build_messages(self, prompt: str, context: str = "") -> list:
        """Build the messages list for Ollama, shared by blocking and streaming methods."""
        messages = [{"role": "system", "content": self.system_prompt}]
        if context:
            messages.append({"role": "user", "content": f"LOCATION DATA:\n{context}"})
            messages.append({"role": "assistant", "content": "I've reviewed the data. What would you like to know?"})
        messages.extend(self.chat_history[-4:])
        messages.append({"role": "user", "content": prompt})
        return messages

    def _stream_ollama(self, prompt: str, context: str = ""):
        """
        Generator: yields token strings one at a time from Ollama's streaming API.
        Works with FastAPI's StreamingResponse.
        """
        import json as _json
        messages = self._build_messages(prompt, context)
        full_response = []

        try:
            with requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": 0.65, "num_predict": 350}
                },
                stream=True,
                timeout=120
            ) as resp:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    chunk = _json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_response.append(token)
                        yield token
                    if chunk.get("done"):
                        break

        except requests.exceptions.Timeout:
            yield "\n[Error: Ollama timed out]"
        except Exception as e:
            yield f"\n[Error: {e}]"

        # Save full response to history
        self.chat_history.append({"role": "user", "content": prompt})
        self.chat_history.append({"role": "assistant", "content": "".join(full_response)})

    def analyze_risk(self, data: Dict, fos: float) -> str:
        """Generate initial risk analysis (blocking)"""
        context = self._format_context(data, fos)
        prompt = "Based on this data, provide a comprehensive landslide risk assessment. Include risk level, key concerns, and safety recommendations."
        self.chat_history = []
        return self._call_ollama(prompt, context)

    def stream_analysis(self, data: Dict, fos: float):
        """Stream risk analysis token-by-token"""
        context = self._format_context(data, fos)
        prompt = "Based on this data, provide a comprehensive landslide risk assessment. Include risk level, key concerns, and safety recommendations."
        self.chat_history = []
        return self._stream_ollama(prompt, context)

    def stream_followup(self, question: str, context: str = ""):
        """Stream answer to a follow-up question token-by-token, with zone context injected."""
        if context:
            # Inject a reminder of zone facts before the user question
            full_prompt = (
                f"[Zone context reminder: {context.strip()}]\n\n"
                f"User question: {question}"
            )
        else:
            full_prompt = question
        return self._stream_ollama(full_prompt)

    def _format_context(self, data: Dict, fos: float) -> str:
        swi_line = (
            f"- Soil Water Index (SWI): {data.get('swi', 'N/A')} mm "
            f"(Saturation: {data.get('soil_saturation', 'N/A')}% of {data.get('field_capacity', 'N/A')}mm capacity)"
            if data.get('swi') is not None else ""
        )
        return f"""
- Location: {data.get('location_name', 'Unknown')}
- Slope: {data.get('slope', 'N/A')} degrees
- Soil Type: {data.get('soil_type', 'N/A')}
- 7-day Rainfall: {data.get('rainfall_mm', 'N/A')} mm
{swi_line}
- Vegetation (NDVI): {data.get('ndvi', 'N/A')}
- Factor of Safety (FoS): {fos}
- PREDICTION MODEL Risk Level: {data.get('risk_level', 'N/A')}
- PREDICTION MODEL Probability: {data.get('probability', 'N/A')}%
        """

    def clear_history(self):
        """Clear conversation history"""
        self.chat_history = []


# Singleton instance for the app
_expert_instance = None

def get_expert_analysis(data: Dict, fos_data: Dict, user_question: Optional[str] = None) -> str:
    """
    Main entry point for the FastAPI app.
    fos_data: Expected format {"factor_of_safety": 1.2}
    """
    global _expert_instance
    if _expert_instance is None:
        # Auto-detect best available model
        OLLAMA_URL = "http://localhost:11434"
        try:
            resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            available = [m['name'].split(':')[0] for m in resp.json().get('models', [])]
            if 'llama3.1' in available:
                model = 'llama3.1'
            elif 'llama3' in available:
                model = 'llama3'
            else:
                model = available[0] if available else 'llama3'
        except Exception:
            model = 'llama3'
        
        print(f"[Expert Agent] Using model: {model}")
        _expert_instance = ExpertGeologist(model_name=model)
    
    fos = fos_data.get("factor_of_safety", 1.5)
    
    if user_question:
        return _expert_instance.ask_followup(user_question)
    else:
        return _expert_instance.analyze_risk(data, fos)

# Quick test
if __name__ == "__main__":
    print("=" * 60)
    print("Testing Expert Geologist with Ollama")
    print("=" * 60)
    
    agent = ExpertGeologist(model_name="llama3")
    
    # Test data
    test_data = {
        "location_name": "Wayanad District, Kerala",
        "slope": 35,
        "soil_type": "Laterite",
        "rainfall_mm": 180,
        "ndvi": 0.45
    }
    test_fos = 0.85
    
    print("\n📊 Analyzing risk for test location...")
    analysis = agent.analyze_risk(test_data, test_fos)
    print("\n" + "=" * 60)
    print("EXPERT ANALYSIS:")
    print("=" * 60)
    print(analysis)
    
    print("\n\n📝 Testing follow-up question...")
    followup = agent.ask_followup("What specific precautions should residents take?")
    print("\n" + "=" * 60)
    print("FOLLOW-UP RESPONSE:")
    print("=" * 60)
    print(followup)
