from base_agent import DebateAgent
from knowledge_integration import retrieve_knowledge
import logging

logger = logging.getLogger("CriticalAgent")

class CriticalAgent(DebateAgent):
    """Critical Agent focused on logical analysis, risk assessment, and ethical considerations.
    
    This agent brings analytical rigor to debates, scrutinizing claims and proposals
    for logical consistency, potential risks, and ethical implications. It ensures
    that blind spots and weaknesses in approaches are identified and addressed.
    """
    
    def __init__(self, model="gpt-4o"):
        """Initialize the Critical Agent with relevant expertise and personality traits.
        
        Args:
            model (str): LLM model to use, defaults to "gpt-4o"
        """
        super().__init__(
            name="Sage_Critical",
            role="Critical Analyst",
            expertise=[
                "risk assessment", 
                "logical analysis", 
                "ethical evaluation", 
                "systems thinking",
                "cognitive bias identification"
            ],
            thinking_style="analytical and critical",
            priorities=[
                "logical consistency", 
                "risk mitigation", 
                "ethical considerations", 
                "long-term viability",
                "unintended consequences"
            ],
            personality_traits=[
                "analytical", 
                "thorough", 
                "skeptical", 
                "principled",
                "detail-oriented"
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
        logger.info(f"CriticalAgent is generating an argument for '{topic}'")
        
        try:
            # Try to retrieve relevant knowledge
            knowledge = retrieve_knowledge(topic)
            
            if knowledge and len(knowledge) > 0:
                logger.info(f"Knowledge retrieved: {len(knowledge)} items")
                
                # Format the knowledge references
                knowledge_text = "\n".join([f"- {k[:150]}..." for k in knowledge[:3]])
                
                # Use reference format for consistency with knowledge integration pattern
                return f"[REF: risks and challenges of {topic}]"
            else:
                logger.warning(f"No knowledge found for '{topic}', using reference request")
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {str(e)}")
        
        # Use reference request to trigger knowledge lookup in the debate system
        return f"[REF: ethical considerations in {topic}]"