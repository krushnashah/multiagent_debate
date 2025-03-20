from base_agent import DebateAgent
from knowledge_integration import retrieve_knowledge
import logging

logger = logging.getLogger("TechnicalAgent")

class TechnicalAgent(DebateAgent):
    """Technical expert agent focused on implementation feasibility, efficiency, and technical innovation.
    
    This agent brings deep technical expertise to debates, evaluating solutions
    for technical feasibility, performance characteristics, and architectural soundness.
    It grounds discussions in technical reality and implementation considerations.
    """
    
    def __init__(self, model="gpt-4o"):
        """Initialize the Technical Agent with relevant expertise and personality traits.
        
        Args:
            model (str): LLM model to use, defaults to "gpt-4o"
        """
        super().__init__(
            name="DrAda_Technical",
            role="Technical Expert",
            expertise=[
                "software engineering", 
                "system architecture", 
                "data science", 
                "AI/ML",
                "technical implementation"
            ],
            thinking_style="analytical and systematic",
            priorities=[
                "technical feasibility", 
                "efficiency", 
                "scalability", 
                "robustness",
                "maintainability"
            ],
            personality_traits=[
                "logical", 
                "detail-oriented", 
                "systematic", 
                "pragmatic",
                "solution-oriented"
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
        logger.info(f"TechnicalAgent is generating an argument for '{topic}'")
        
        try:
            # Try to retrieve relevant knowledge
            knowledge = retrieve_knowledge(topic)
            
            if knowledge and len(knowledge) > 0:
                logger.info(f"Knowledge retrieved: {len(knowledge)} items")
                
                # Format the knowledge references
                knowledge_text = "\n".join([f"- {k[:150]}..." for k in knowledge[:3]])
                
                # Use reference format for consistency with knowledge integration pattern
                return f"[REF: technical implementation of {topic}]"
            else:
                logger.warning(f"No knowledge found for '{topic}', using reference request")
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {str(e)}")
        
        # Use reference request to trigger knowledge lookup in the debate system
        return f"[REF: technical approaches to {topic}]"