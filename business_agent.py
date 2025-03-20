from base_agent import DebateAgent
from knowledge_integration import retrieve_knowledge
import logging

logger = logging.getLogger("BusinessAgent")

class BusinessAgent(DebateAgent):
    """Business expert agent focused on market viability, profitability, and strategic alignment.
    
    This agent brings a pragmatic business perspective to debates, focusing on
    commercial implications, market analysis, and business strategy. It evaluates
    ideas primarily based on their potential for sustainable business success.
    """
    
    def __init__(self, model="gpt-4o"):
        """Initialize the Business Agent with relevant expertise and personality traits.
        
        Args:
            model (str): LLM model to use, defaults to "gpt-4o"
        """
        super().__init__(
            name="Morgan_Business",
            role="Business Strategist",
            expertise=[
                "market analysis", 
                "business modeling", 
                "strategic planning", 
                "ROI optimization",
                "competitive landscape assessment"
            ],
            thinking_style="strategic and pragmatic",
            priorities=[
                "market viability", 
                "profitability", 
                "competitive advantage", 
                "scalability",
                "long-term sustainability"
            ],
            personality_traits=[
                "pragmatic", 
                "results-oriented", 
                "big-picture thinker", 
                "decisive",
                "data-driven"
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
        logger.info(f"BusinessAgent is generating an argument for '{topic}'")
        
        try:
            # Try to retrieve relevant knowledge
            knowledge = retrieve_knowledge(topic)
            
            if knowledge and len(knowledge) > 0:
                logger.info(f"Knowledge retrieved: {len(knowledge)} items")
                
                # Format the knowledge references
                knowledge_text = "\n".join([f"- {k[:150]}..." for k in knowledge[:3]])
                
                # Use reference format for consistency with knowledge integration pattern
                return f"[REF: business applications of {topic}]"
            else:
                logger.warning(f"No knowledge found for '{topic}', using reference request")
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {str(e)}")
        
        # Use reference request to trigger knowledge lookup in the debate system
        return f"[REF: market viability of {topic}]"