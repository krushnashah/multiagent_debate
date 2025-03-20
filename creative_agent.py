from base_agent import DebateAgent
from knowledge_integration import retrieve_knowledge
import logging

logger = logging.getLogger("CreativeAgent")

class CreativeAgent(DebateAgent):
    """Creative expert agent focused on innovation, user experience, and novel approaches.
    
    This agent brings a divergent thinking approach to debates, emphasizing innovative
    solutions, user-centered design, and creative problem-solving methods. It explores
    possibilities beyond conventional thinking.
    """
    
    def __init__(self, model="gpt-4o"):
        """Initialize the Creative Agent with relevant expertise and personality traits.
        
        Args:
            model (str): LLM model to use, defaults to "gpt-4o"
        """
        super().__init__(
            name="Nova_Creative",
            role="Innovation Specialist",
            expertise=[
                "design thinking", 
                "creative problem-solving", 
                "user experience", 
                "trend forecasting",
                "human-centered design"
            ],
            thinking_style="divergent and explorative",
            priorities=[
                "innovation", 
                "user-centricity", 
                "adaptability", 
                "emotional impact",
                "originality"
            ],
            personality_traits=[
                "imaginative", 
                "curious", 
                "empathetic", 
                "open-minded",
                "optimistic"
            ],
            model=model
        )

    def generate_argument(self, topic):
        """Generate an argument for the debate topic, incorporating knowledge retrieval.
        
        Args:
            topic (str): The debate topic/problem statement
            
        Returns:
            str: The generated argument with incorporated knowledge
        """
        logger.info(f"CreativeAgent is generating an argument for '{topic}'")
        
        try:
            # Try to retrieve relevant knowledge
            knowledge = retrieve_knowledge(topic)
            
            if knowledge and len(knowledge) > 0:
                logger.info(f"Knowledge retrieved: {len(knowledge)} items")
                
                # Format the knowledge references
                knowledge_text = "\n".join([f"- {k[:150]}..." for k in knowledge[:3]])
                
                # Use reference format for consistency with knowledge integration pattern
                return f"[REF: creative innovations in {topic}]"
            else:
                logger.warning(f"No knowledge found for '{topic}', using reference request")
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {str(e)}")
        
        # Use reference request to trigger knowledge lookup in the debate system
        return f"[REF: creative approaches to {topic}]"