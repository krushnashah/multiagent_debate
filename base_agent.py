import os
import autogen
from dotenv import load_dotenv
from knowledge_integration import retrieve_knowledge
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger("BaseAgent")

class DebateAgent(autogen.AssistantAgent):
    """Base class for all debate agents using Autogen.
    
    This class provides the foundation for specialized agents that engage
    in structured debates with distinct personalities and expertise domains.
    """

    def __init__(self, name, role, expertise, thinking_style, priorities, personality_traits, model="gpt-4o"):
        """Initialize a base agent with core attributes.
        
        Args:
            name (str): Unique identifier for the agent
            role (str): Professional role the agent embodies
            expertise (list): Areas of specialized knowledge
            thinking_style (str): Characteristic thinking approach
            priorities (list): Key values or priorities
            personality_traits (list): Defining personality characteristics
            model (str): LLM model to use, defaults to "gpt-4o"
        """
        self._original_system_message = f"""
        You are {name}, a {role} with expertise in {', '.join(expertise)}. 
        Your thinking style is {thinking_style}. You prioritize {', '.join(priorities)}. 
        Your personality is described as {', '.join(personality_traits)}.
        
        Guidelines for participation:
        - Engage in structured debates based on your unique perspective
        - Provide constructive critiques of other perspectives
        - Respond to criticism thoughtfully
        - Identify common ground between differing viewpoints
        - Contribute to a final synthesis and report
        
        Always maintain your distinct voice and perspective throughout the debate.
        """
        
        super().__init__(
            name=name,
            system_message=self._original_system_message,
            llm_config={"model": model, "api_key": os.getenv("OPENAI_API_KEY")}
        )
    
    def update_system_message(self, new_message):
        """Update the agent's system message.
        
        Autogen's LLMConfig doesn't have a system_message field directly,
        so we need to recreate the agent with the new system message.
        
        Args:
            new_message (str): The new system message
        """
        # Store the new message for future reference
        self._original_system_message = new_message
        
        # In Autogen, we can't modify the system message directly through llm_config
        # We need to recreate the agent with a new message
        # This is a workaround that makes a shallow copy of llm_config
        config = dict(self.llm_config)
        
        # Create a new AssistantAgent with the updated message
        self.__class__ = autogen.AssistantAgent
        autogen.AssistantAgent.__init__(
            self,
            name=self.name,
            system_message=new_message,
            llm_config=config
        )
        
        logger.info(f"Updated system message for {self.name}")
    
    def generate_argument(self, topic):
        """Generate an initial argument for the debate topic, incorporating knowledge retrieval.
        
        Args:
            topic (str): The debate topic
            
        Returns:
            str: The generated argument with incorporated knowledge
        """
        logger.info(f"{self.name} is generating an argument for '{topic}'")
        
        # Try to retrieve relevant knowledge
        try:
            knowledge = retrieve_knowledge(topic)
            
            if knowledge and len(knowledge) > 0:
                logger.info(f"Knowledge retrieved: {len(knowledge)} items")
                
                # Format the knowledge references
                knowledge_text = "\n".join([f"- {k[:150]}..." for k in knowledge[:2]])
                
                # Construct an argument that incorporates this knowledge
                # Use the agent's expertise and priorities to frame the response
                agent_role = self._original_system_message.split('a ')[1].split(' with')[0]
                agent_priorities = self._original_system_message.split('prioritize ')[1].split('.')[0]
                
                # Use reference format for consistency with knowledge integration pattern
                return f"[REF: {topic} from {agent_role}'s perspective]"
        except Exception as e:
            logger.error(f"Error in {self.name}'s knowledge retrieval: {str(e)}")
        
        # If knowledge retrieval fails or returns nothing, use explicit reference request
        logger.info(f"{self.name} using reference request in argument")
        return f"[REF: {topic}]"