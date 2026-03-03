- Once langgraph is more figuredOut move to langchain
- Add store for semantic search of memory by the agents, this is as opposed to dumping memory in the message, IMPORTANT TO TRY, see https://docs.langchain.com/oss/python/langgraph/persistence
- Create an evaluation agent
- Try out the agent chat UI
- Explore langsmoth 
- The autonomous agent will benefit from the interrupt. Test how interrupt works with API loop
- Provide interrupt to the aml expert in copilot mode, to clarify intent. Important note: interrupt does not resume from the node, so it needs to be handled properly, see https://docs.langchain.com/oss/python/langgraph/interrupts



Requirement | Supervisor | LangGraph | Winner |                                               
|-------------|-----------|-----------|--------|                                                
| Get data | ✅ Works | ✅ Works | Tie |                                                        
| Ask user for clarification | ✅ Natural | ✅ With state | Tie |                               
| Give AML guidance | ✅ Works | ✅ Works | Tie |                                               
| **Guaranteed second opinion** | ❌ Optional | ✅ Guaranteed | **LangGraph** |                 
| Autonomous mode | ⚠️ Separate agent | ✅ Routing path | **LangGraph** |                       
| **Review loops** | ❌ Fragile | ✅ Deterministic | **LangGraph** |                            
| **Audit trail** | ⚠️ LLM reasoning | ✅ Code-defined | **LangGraph** |                        
| **Loop prevention** | ⚠️ Relies on LLM | ✅ Explicit limits | **LangGraph** |                 
| Conversation flexibility | ✅ Very flexible | ⚠️ Less flexible | **Supervisor** |             
| Simplicity for basic queries | ✅ Less boilerplate | ⚠️ More boilerplate | **Supervisor** |