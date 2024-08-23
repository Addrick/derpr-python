derpr: an easily extensible chat-based LLM request system
This is a personal project that has had an ever-expanding feature scope so it requires a bit of setup, primarily 
creating an api_keys.py file under \stuff and adding the relevant keys there as required. System is planned for overhaul
once I'm happier with the core feature set. 


Current features:
- supports OpenAI, Anthropic, Google and local koboldcpp inference (change model on the fly)
- supports multiple requests asynchronously
- handles 'personas', which contain various tools for customizing response habits:
  - prompt: basic personality information for agent
  - model: determines which language engine to query
  - context limit: number of previous discord messages read and included in requests as chat history, system commands are not included (ie changing context length)
  - token limit: number of tokens the model is allowed to generate on response
- address different personas by beginning your message with their name (todo: also replies)
- persona will always reply to a channel with a name matching the persona
- 'derpr help' will give a list of active personas and commands for addressing the persona handler system directly.

Bot commands are simple text statements to accommodate eventual speech support. Below are current commands and they are 
listed when you ask any persona 'help':

hello (start new conversation), - dynamically increases context window to include all messages in conversation after 'hello'
goodbye (end conversation), - exits conversation, returns context window to default
remember <+prompt>, - adds information to end of prompt
what prompt/model/personas/context/tokens, - returns current value for desired parameter
set prompt/model/context/tokens, - sets value for specified parameter. Models must exactly match an available model from 'what models'
add <persona> <prompt>, - adds new persona with default parameters
delete <persona>, - deletes persona
save, - write changes to prompts/parameters to file for preservation across restarts (sometimes called automatically, like on creating new persona) WIP
update_models, - query services to retrieve an up-to-date list of available models (Anthropic does not support this)
dump_last - dumps a raw json of the previous request sent to the system to view parameters and history/context for debugging

start_koboldcpp, - starts koboldcpp service. Buggy, WIP
stop_koboldcpp, - stops koboldcpp service. Buggy WIP
check_koboldcpp, - usually doesn't work, WIP
query_generation, - request dump of partially generated response from koboldcpp during generation
restart_app, - restart koboldcpp, WIP