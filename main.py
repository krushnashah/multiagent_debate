"""
Main script to run the Multi-Agent Ideation and Debate System.
Simplified for debugging and reliability.
"""

import os
import sys
import argparse
import time
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debate_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DebateMain")

# Add the current directory to the path to make imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
logger.info(f"Added {current_dir} to Python path")

try:
    # Import agent modules
    logger.info("Importing agent modules...")
    from business_agent import BusinessAgent
    from creative_agent import CreativeAgent
    from critical_agent import CriticalAgent
    from technical_agent import TechnicalAgent
    from debate import run_semi_agentic_debate
    logger.info("Successfully imported all required modules")
except ImportError as e:
    logger.error(f"Failed to import required modules: {str(e)}")
    sys.exit(1)

def parse_arguments():
    """Parse command line arguments for the debate system."""
    logger.info("Parsing command line arguments...")
    parser = argparse.ArgumentParser(
        description='Multi-Agent Ideation and Debate System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python directmain.py --problem "How can AI improve healthcare access in rural areas?"
  python directmain.py --problem "How to make online education more engaging?" --agents business,creative
  python directmain.py --problem "How to reduce carbon emissions in urban areas?" --output results_carbon
  python directmain.py --problem "How can AI improve creative design?" --agents creative,business --use_knowledge
        """
    )
    
    parser.add_argument(
        '--problem', 
        type=str, 
        default="How can we make AI-generated content more reliable for professional use?",
        help='The problem statement or topic for debate'
    )
    
    parser.add_argument(
        '--agents', 
        type=str, 
        default="business,creative",  # Default to just 2 agents for faster testing
        help='Comma-separated list of agents to include (business,creative,critical,technical)'
    )
    
    parser.add_argument(
        '--output', 
        type=str, 
        help='Custom output directory name (default: timestamp-based)'
    )
    
    parser.add_argument(
        '--model', 
        type=str, 
        default="gpt-4o",
        help='LLM model to use for agents (default: gpt-4o)'
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true', 
        help='Enable extra debug output'
    )
    
    # Knowledge integration options
    parser.add_argument(
        '--use_knowledge', 
        action='store_true', 
        help='Enable knowledge integration from documents and web'
    )
    
    parser.add_argument(
        '--document_dir', 
        type=str, 
        default="documents",
        help='Directory containing knowledge base documents (PDFs, DOCXs, TXTs)'
    )
    
    parser.add_argument(
        '--no_web_search',
        action='store_true',
        help='Disable web search fallback (only use local documents and AI generation)'
    )
    
    parser.add_argument(
        '--no_ai_generation',
        action='store_true',
        help='Disable AI generation fallback (only use local documents and web search)'
    )

    parser.add_argument(
    '--interactive',
    action='store_true',
    help='Create custom agents interactively'
    )
    
    args = parser.parse_args()
    logger.info(f"Arguments parsed: {args}")
    return args

def create_agent_interactively(model):
    """Create an agent through interactive prompts."""
    print("\n--- Creating Custom Agent ---")
    
    name = input("Agent name: ")
    role = input("Professional role: ")
    
    expertise = input("Areas of expertise (comma-separated): ")
    expertise = [e.strip() for e in expertise.split(',')]
    
    thinking_style = input("Thinking style: ")
    
    priorities = input("Priorities (comma-separated): ")
    priorities = [p.strip() for p in priorities.split(',')]
    
    personality_traits = input("Personality traits (comma-separated): ")
    personality_traits = [t.strip() for t in personality_traits.split(',')]
    
    # Import at function level to avoid circular imports
    from base_agent import DebateAgent
    
    return DebateAgent(
        name=name,
        role=role,
        expertise=expertise,
        thinking_style=thinking_style,
        priorities=priorities,
        personality_traits=personality_traits,
        model=model
    )

def main():
    """Main function to run the debate system."""
    logger.info("Starting Multi-Agent Debate System...")
    
    # Ensure OpenAI API key is set
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("Error: OPENAI_API_KEY not found in environment variables or .env file")
        sys.exit(1)
    logger.info("API key loaded successfully")
    
    # Parse arguments
    args = parse_arguments()
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Configure knowledge integration
    knowledge_config = None
    if args.use_knowledge:
        # Create document directory if it doesn't exist
        document_dir = os.path.abspath(args.document_dir)
        os.makedirs(document_dir, exist_ok=True)
        
        logger.info(f"Knowledge integration enabled. Using documents from: {document_dir}")
        # Set environment variable for document directory
        os.environ["DOCUMENT_DIR"] = document_dir
        
        # Check if directory contains documents
        doc_files = []
        if os.path.exists(document_dir):
            doc_files = [f for f in os.listdir(document_dir) 
                        if os.path.isfile(os.path.join(document_dir, f)) 
                        and f.lower().endswith(('.pdf', '.docx', '.txt'))]
        
        if not doc_files:
            logger.warning(f"No document files (.pdf, .docx, .txt) found in '{document_dir}'.")
            logger.info("Will rely on web search and AI generation fallbacks.")
        else:
            logger.info(f"Found {len(doc_files)} document files: {', '.join(doc_files[:5])}" + 
                       (f" (and {len(doc_files)-5} more)" if len(doc_files) > 5 else ""))
        
        knowledge_config = {
            "document_dir": document_dir,
            "use_web_search": not args.no_web_search,
            "use_ai_generation": not args.no_ai_generation
        }
        
        # Log fallback configuration
        logger.info(f"Knowledge fallbacks: Web search {'disabled' if args.no_web_search else 'enabled'}, " + 
                   f"AI generation {'disabled' if args.no_ai_generation else 'enabled'}")
        
        # Check if Google API key is available for web search
        if not args.no_web_search and not os.getenv("GOOGLE_API_KEY") and not os.getenv("GOOGLE_CX"):
            logger.warning("GOOGLE_API_KEY or GOOGLE_CX not found in environment. Web search fallback may not work.")
    else:
        logger.info("Knowledge integration disabled.")
    
    # Parse agent selection
    logger.info("Initializing selected agents...")
    selected_agent_types = [a.strip().lower() for a in args.agents.split(',')]
    
    # Map of available agents
    agent_map = {
        "business": BusinessAgent,
        "creative": CreativeAgent,
        "critical": CriticalAgent,
        "technical": TechnicalAgent
    }
    
    # Initialize agents
    agents = []

    # Interactive mode for agent creation
    if args.interactive:
        print("\n=== Interactive Agent Creation ===")
        
        # Optionally update the problem statement
        custom_topic = input(f"Enter the debate topic [{args.problem}]: ")
        if custom_topic:
            args.problem = custom_topic
        
        # Create agents interactively
        print("\nYou'll need to create at least 2 agents for the debate.")
        while True:
            # Allow user to choose between built-in and custom agents
            agent_type = input("\nCreate (b)uilt-in or (c)ustom agent? (b/c): ").lower()
            
            if agent_type.startswith('b'):
                # Show available built-in agents
                print("Available agents: business, creative, critical, technical")
                agent_choice = input("Which built-in agent? ").lower().strip()
                
                if agent_choice in agent_map:
                    agents.append(agent_map[agent_choice](model=args.model))
                    print(f"Added {agent_choice} agent")
                else:
                    print(f"Unknown agent type: {agent_choice}")
            else:
                # Create custom agent
                agent = create_agent_interactively(args.model)
                agents.append(agent)
                print(f"Added custom agent: {agent.name}")
            
            # Check if we have enough agents
            if len(agents) >= 2 and input("\nAdd another agent? (y/n): ").lower() != 'y':
                break
    else:
        # Parse agent selection (original code)
        selected_agent_types = [a.strip().lower() for a in args.agents.split(',')]
        
        # Map of available agents
        agent_map = {
            "business": BusinessAgent,
            "creative": CreativeAgent,
            "critical": CriticalAgent,
            "technical": TechnicalAgent
        }
        
        # Initialize selected agents
        for agent_type in selected_agent_types:
            if agent_type in agent_map:
                logger.info(f"Initializing {agent_type} agent...")
                try:
                    # Initialize with specified model
                    agent = agent_map[agent_type](model=args.model)
                    agents.append(agent)
                    logger.info(f"Successfully initialized {agent.name}")
                except Exception as e:
                    logger.error(f"Error initializing {agent_type} agent: {str(e)}")
                    sys.exit(1)
            else:
                logger.warning(f"Unknown agent type '{agent_type}'. Skipping.")
    
    # Ensure we have at least 2 agents
    if len(agents) < 2:
        logger.error("Error: At least 2 agents are required for a debate.")
        logger.error("Available agent types: business, creative, critical, technical")
        sys.exit(1)

    # Print system info
    logger.info("\n" + "="*50)
    logger.info("Multi-Agent Ideation and Debate System")
    logger.info("="*50)
    logger.info(f"Problem Statement: \"{args.problem}\"")
    logger.info(f"Using model: {args.model}")
    logger.info(f"Output directory: {args.output if args.output else 'Auto-generated (timestamp)'}")
    if args.use_knowledge:
        logger.info(f"Knowledge integration: Enabled (document_dir={args.document_dir})")
    
    # Print agent information
    logger.info(f"\nInitialized {len(agents)} agents for debate:")
    for agent in agents:
        role = agent.system_message.split("a ")[1].split(" with")[0] if "with" in agent.system_message else "Agent"
        logger.info(f"- {agent.name}: {role}")

    logger.info("\nStarting semi-agentic debate process...")
    
    # Run the debate
    try:
        logger.info("Calling run_semi_agentic_debate()...")
        start_time = time.time()
        
    
        output_dir, results = run_semi_agentic_debate(
            problem_statement=args.problem, 
            agents=agents,
            output_dir=args.output,
            knowledge_config=knowledge_config  # Pass knowledge configuration
        )
        
        end_time = time.time()
        duration = end_time - start_time
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        logger.info(f"\nDebate completed successfully!")
        logger.info(f"Total runtime: {int(hours)}h {int(minutes)}m {int(seconds)}s")
        logger.info(f"All output files are available in: {output_dir}")
        
        # Display path to the summary file for convenience
        summary_path = os.path.join(output_dir, "debate_summary.md")
        logger.info(f"\nTo view the debate summary:")
        logger.info(f"cat {summary_path}")
        
        # Display knowledge references if they exist
        if args.use_knowledge:
            references_path = os.path.join(output_dir, "knowledge_references.md")
            if os.path.exists(references_path):
                logger.info(f"\nTo view knowledge references used:")
                logger.info(f"cat {references_path}")
        
    except Exception as e:
        logger.error(f"\nError during debate process: {str(e)}")
        import traceback
        traceback.print_exc()
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}")
        import traceback
        traceback.print_exc()
        logger.critical(traceback.format_exc())
        sys.exit(1)