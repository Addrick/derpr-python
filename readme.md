derpr: a Discord-based LLM wrapper for prototyping prompts

- supports OpenAI and Google Bard ('text-bison-001') models, local inference planned next
- handles 'personas', which contain various tools for customizing response habits:
  - prompt: basic personality information for agent
  - model: determines which language engine to query
  - context limit: number of previous discord messages read and included in requests as chat history
  - token limit: number of tokens the model is allowed to generate
- address different personas by beginning your message with their name
- 'derpr help' will give a list of commands for addressing the persona handler directly