"""
Semi-agentic debate system that balances reliability with agent autonomy.
This approach preserves more agent autonomy while ensuring the debate completes successfully.
"""

import os
import json
import time
import logging
import re
from collections import Counter
from openai import OpenAI
from dotenv import load_dotenv

# Import knowledge integration module
from knowledge_integration import KnowledgeIntegration, process_reference_requests, retrieve_knowledge

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("debate.log"), logging.StreamHandler()])
logger = logging.getLogger("DebateSystem")

def ensure_knowledge_in_agent_message(message, agent_name, knowledge_integration, phase, problem_statement):
    """
    Ensure the agent's message contains reference to knowledge.
    If no references are detected, explicitly add a reference request.
    
    Args:
        message (str): The agent's message
        agent_name (str): Name of the agent
        knowledge_integration: Knowledge integration object
        phase (str): Current debate phase
        problem_statement (str): The debate topic
        
    Returns:
        str: Message with knowledge integration
    """
    # Check if the message already contains reference requests
    if re.search(r'\[REF:(.*?)\]', message) or '[Reference for' in message:
        logger.info(f"{agent_name} already included reference requests in {phase}")
        return message
    
    # If not, process an explicit reference request
    if knowledge_integration:
        logger.info(f"Adding knowledge reference for {agent_name} in {phase}")
        
        # Create reference query based on agent name and phase
        if "Nova_Creative" in agent_name:
            query = f"creative innovations in {problem_statement}"
        elif "Morgan_Business" in agent_name:
            query = f"business applications of {problem_statement}"
        elif "Sage_Critical" in agent_name:
            query = f"risks and challenges of {problem_statement}"
        elif "DrAda_Technical" in agent_name:
            query = f"technical implementation of {problem_statement}"
        else:
            query = problem_statement
            
        # Get knowledge
        results = knowledge_integration.retrieve_knowledge(query)
        
        if results:
            # Add knowledge to the message
            knowledge_text = results[0][:200]  # Truncate for readability
            enhanced_message = (
                f"{message}\n\n"
                f"[Reference for '{query}': {knowledge_text}...]"
            )
            
            # Track this reference
            if hasattr(knowledge_integration, 'client') and hasattr(knowledge_integration.client, 'knowledge_references'):
                knowledge_integration.client.knowledge_references.append({
                    "query": query,
                    "source": results[0][:200] + "..." if len(results[0]) > 200 else results[0],
                    "agent": agent_name,
                    "phase": phase
                })
                
            logger.info(f"Added knowledge reference for {agent_name} in {phase}")
            return enhanced_message
    
    # If we couldn't add a reference, return the original message
    return message

def generate_standard_perspective(agent, client, problem_statement, knowledge_integration):
    """Generate a standard perspective using the OpenAI API with knowledge integration."""
    prompt = f"""
    The moderator has asked you to share your perspective on the following problem:
    
    '{problem_statement}'
    
    Provide your initial thoughts based on your unique expertise and thinking style.
    """
    
    # Add reference request instruction if knowledge integration is enabled
    if knowledge_integration:
        prompt += f"""
        To support your perspective, include at least one specific reference request 
        using [REF: your specific query] syntax.
        
        For example: "I believe [REF: latest innovations in {problem_statement}] 
        will have a significant impact on this area."
        """
    
    prompt += "\nKeep your response under 150 words and focused on your area of expertise."
    
    # Generate the perspective
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": agent.system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300
    )
    
    perspective = response.choices[0].message.content
    
    # Process any reference requests if knowledge integration is enabled
    if knowledge_integration:
        perspective = process_reference_requests(
            perspective, 
            knowledge_integration, 
            agent_name=agent.name, 
            phase="initial_perspective"
        )
        
        # If no reference requests were detected, add one explicitly
        if "[REF:" not in perspective and "[Reference for" not in perspective:
            logger.info(f"Adding explicit reference for {agent.name}")
            perspective = ensure_knowledge_in_agent_message(
                perspective, 
                agent.name, 
                knowledge_integration, 
                "initial_perspective", 
                problem_statement
            )
    
    return perspective

class ModeratorAgent:
    """Simulated moderator agent to guide the debate."""
    
    def __init__(self, problem_statement, knowledge_integration=None):
        self.name = "Moderator"
        self.problem_statement = problem_statement
        self.knowledge_integration = knowledge_integration
        self.system_message = f"""You are a moderator guiding a debate on: '{problem_statement}'.
        Your job is to facilitate discussion, summarize key points, identify common ground,
        and ensure a productive exchange of ideas. Be impartial but incisive, encouraging
        deep exploration of the topic while keeping participants focused.
        
        You can request additional information on a topic by using [REF: your query] syntax.
        For example, to get information about recent AI advancements, use [REF: recent advancements in AI].
        """
    
    def generate_message(self, client, prompt, phase_name, context=None):
        """Generate a message from the moderator based on the given prompt and context."""
        messages = [
            {"role": "system", "content": self.system_message}
        ]
        
        if context:
            messages.append({"role": "user", "content": f"Here's the context so far:\n\n{context}"})
        
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=200
        )
        
        message = response.choices[0].message.content
        
        # Process any reference requests
        if self.knowledge_integration:
            message = process_reference_requests(
                message, 
                self.knowledge_integration, 
                agent_name="Moderator", 
                phase=phase_name
            )
        
        logger.info(f"Moderator generated {phase_name} message")
        return message

def extract_keywords(text, count=5):
    """Extract key terms from text to track concept evolution."""
    # Remove common stop words (a basic implementation)
    stop_words = set(['i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 
                     'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 
                     'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 
                     'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 
                     'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 
                     'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 
                     'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 
                     'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 
                     'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 
                     'through', 'during', 'before', 'after', 'above', 'below', 'to', 
                     'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 
                     'again', 'further', 'then', 'once', 'here', 'there', 'when', 
                     'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 
                     'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 
                     'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 
                     'just', 'don', 'should', 'now'])
    
    # Convert to lowercase and tokenize
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Filter out stop words and single characters
    filtered_words = [word for word in words if word not in stop_words and len(word) > 1]
    
    # Count word frequencies
    word_counts = Counter(filtered_words)
    
    # Return the most common words
    return word_counts.most_common(count)

def analyze_sentiment(client, text):
    """Analyze sentiment of text to track emotional tone."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a sentiment analysis tool. Analyze the following text and return a single number representing the sentiment. Use -1 for very negative, 0 for neutral, and +1 for very positive."},
                {"role": "user", "content": f"Analyze the sentiment of this text: {text}"}
            ],
            max_tokens=50
        )
        
        # Extract the sentiment value
        result = response.choices[0].message.content.strip()
        sentiment = 0
        
        # Try to extract a number
        match = re.search(r'(-?\d+(\.\d+)?)', result)
        if match:
            sentiment = float(match.group(1))
            # Ensure it's within -1 to 1 range
            sentiment = max(-1, min(1, sentiment))
            
        return sentiment
    except Exception as e:
        logger.warning(f"Sentiment analysis failed: {str(e)}")
        return 0  # Default to neutral

def generate_idea_graphs(debate_data, output_dir):
    """Generate simplified textual representation of idea influence patterns."""
    # Create a directory for visualizations
    viz_dir = os.path.join(output_dir, "visualizations")
    os.makedirs(viz_dir, exist_ok=True)
    
    # Extract agent names
    agents = debate_data.get("agents", [])
    
    # Create a simple text-based representation instead of graphical
    graph_text = "# Agent Influence Network\n\n"
    graph_text += "This is a simplified representation of how agents influenced each other:\n\n"
    
    # Add edges based on critiques (who critiqued whom)
    critiques = debate_data.get("phases", {}).get("critiques", {})
    for critic, targets in critiques.items():
        for target in targets:
            graph_text += f"* {critic} → {target} (critique)\n"
    
    # Save the text representation
    graph_path = os.path.join(viz_dir, "influence_network.txt")
    with open(graph_path, "w") as f:
        f.write(graph_text)
    
    return graph_path

def generate_mermaid_diagram(debate_data):
    """Generate a Mermaid diagram showing debate flow and concept evolution."""
    agents = debate_data.get("agents", [])
    perspectives = debate_data.get("phases", {}).get("initial_perspectives", {})
    final_positions = debate_data.get("phases", {}).get("final_positions", {})
    
    # Extract keywords from initial and final positions
    initial_keywords = {}
    final_keywords = {}
    
    for agent, perspective in perspectives.items():
        initial_keywords[agent] = extract_keywords(perspective, 3)
    
    for agent, position in final_positions.items():
        final_keywords[agent] = extract_keywords(position, 3)
    
    # Generate Mermaid diagram
    mermaid = """
graph TD
    Problem[Problem Statement] --> Debate[Structured Debate]
    Debate --> Perspectives[Initial Perspectives]
    Perspectives --> Critiques[Critiques]
    Critiques --> Responses[Responses]
    Responses --> CommonGround[Common Ground]
    CommonGround --> FinalPositions[Final Positions]
    FinalPositions --> Report[Synthesized Report]
    
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:1px;
    classDef problem fill:#d1e7dd,stroke:#333,stroke-width:1px;
    classDef phase fill:#d9e2ef,stroke:#333,stroke-width:1px;
    classDef report fill:#ffeeba,stroke:#333,stroke-width:1px;
    
    class Problem problem;
    class Perspectives,Critiques,Responses,CommonGround,FinalPositions phase;
    class Report report;
    """
    
    # Add agent nodes with keywords
    mermaid += "\n    %% Agent Evolution\n"
    for agent in agents:
        initial_kw = initial_keywords.get(agent, [])
        final_kw = final_keywords.get(agent, [])
        
        # Initial keywords node
        initial_terms = ", ".join([f"'{k[0]}'" for k in initial_kw])
        mermaid += f"    {agent}_initial[{agent}<br>Initial: {initial_terms}]\n"
        
        # Final keywords node
        final_terms = ", ".join([f"'{k[0]}'" for k in final_kw])
        mermaid += f"    {agent}_final[{agent}<br>Final: {final_terms}]\n"
        
        # Connect them
        mermaid += f"    {agent}_initial --> {agent}_final\n"
        
        # Connect to debate phases
        mermaid += f"    Perspectives --> {agent}_initial\n"
        mermaid += f"    {agent}_final --> FinalPositions\n"
    
    return mermaid

def generate_idea_evolution_visualization(perspectives, critiques, responses, common_ground, final_positions, client):
    """
    Generate advanced visualizations of how ideas evolved throughout the debate.
    This enhanced version provides multiple views of the debate evolution.
    """
    # Basic text visualization (from original code)
    visualization = """## How Ideas Evolved Through the Debate

This visualization tracks how each expert's thinking developed throughout the debate process.

"""
    
    # Track each agent's journey with additional metrics
    agent_keywords = {}
    agent_sentiments = {}
    key_concepts = set()
    
    for agent_name in perspectives.keys():
        visualization += f"### {agent_name}'s Journey\n\n"
        
        # Initial perspective (abbreviated)
        initial = perspectives[agent_name]
        visualization += f"**Initial Perspective:**\n> {initial[:150]}...\n\n"
        
        # Extract keywords from initial perspective
        initial_keywords = extract_keywords(initial)
        agent_keywords[agent_name] = {"initial": initial_keywords}
        key_concepts.update([kw[0] for kw in initial_keywords])
        
        # Analyze sentiment
        initial_sentiment = analyze_sentiment(client, initial)
        agent_sentiments[agent_name] = {"initial": initial_sentiment}
        
        # Visualization of key terms
        visualization += "**Key Terms:**\n"
        for term, count in initial_keywords:
            visualization += f"- {term} ({count})\n"
        visualization += "\n"
        
        # Sentiment indicator
        sentiment_text = "Positive" if initial_sentiment > 0.3 else ("Negative" if initial_sentiment < -0.3 else "Neutral")
        visualization += f"**Tone:** {sentiment_text} ({initial_sentiment:.2f})\n\n"
        
        # Critiques received
        visualization += "**Critiques Received:**\n"
        received_any = False
        critique_text = ""
        for critic, targets in critiques.items():
            if agent_name in targets:
                critique = targets[agent_name]
                visualization += f"- From {critic}: {critique[:100]}...\n"
                critique_text += critique + " "
                received_any = True
        if not received_any:
            visualization += "- *No direct critiques received*\n"
        visualization += "\n"
        
        # Analyze critiques if received
        if received_any:
            critique_keywords = extract_keywords(critique_text)
            agent_keywords[agent_name]["critiques"] = critique_keywords
            critique_sentiment = analyze_sentiment(client, critique_text)
            agent_sentiments[agent_name]["critiques"] = critique_sentiment
        
        # Their response
        if agent_name in responses:
            response_text = responses[agent_name]['response']
            visualization += f"**Response to Critiques:**\n> {response_text[:150]}...\n\n"
            
            # Analyze response
            response_keywords = extract_keywords(response_text)
            agent_keywords[agent_name]["response"] = response_keywords
            response_sentiment = analyze_sentiment(client, response_text)
            agent_sentiments[agent_name]["response"] = response_sentiment
            
            # Show keyword changes
            visualization += "**Key Terms Shift:**\n"
            for term, count in response_keywords:
                visualization += f"- {term} ({count})\n"
            visualization += "\n"
        
        # Common ground they identified
        if agent_name in common_ground:
            common_text = common_ground[agent_name]
            visualization += f"**Common Ground Identified:**\n> {common_text[:150]}...\n\n"
            
            # Analyze common ground
            common_keywords = extract_keywords(common_text)
            agent_keywords[agent_name]["common"] = common_keywords
            common_sentiment = analyze_sentiment(client, common_text)
            agent_sentiments[agent_name]["common"] = common_sentiment
        
        # Final position (abbreviated)
        if agent_name in final_positions:
            final_text = final_positions[agent_name]
            visualization += f"**Final Position:**\n> {final_text[:200]}...\n\n"
            
            # Analyze final position
            final_keywords = extract_keywords(final_text)
            agent_keywords[agent_name]["final"] = final_keywords
            key_concepts.update([kw[0] for kw in final_keywords])
            final_sentiment = analyze_sentiment(client, final_text)
            agent_sentiments[agent_name]["final"] = final_sentiment
            
            # Show keyword evolution
            visualization += "**Final Key Terms:**\n"
            for term, count in final_keywords:
                visualization += f"- {term} ({count})\n"
            visualization += "\n"
            
            # Show sentiment evolution if we have both initial and final
            if "initial" in agent_sentiments[agent_name] and "final" in agent_sentiments[agent_name]:
                init_sentiment = agent_sentiments[agent_name]["initial"]
                final_sentiment = agent_sentiments[agent_name]["final"]
                change = final_sentiment - init_sentiment
                direction = "more positive" if change > 0.2 else ("more negative" if change < -0.2 else "relatively unchanged")
                visualization += f"**Sentiment Evolution:** Tone became {direction} ({change:.2f} shift)\n\n"
        
        # Generate concept evolution
        visualization += "**Key Concept Evolution:**\n"
        
        # Compare initial and final keywords if available
        if "initial" in agent_keywords[agent_name] and "final" in agent_keywords[agent_name]:
            initial_kw = {k[0]: k[1] for k in agent_keywords[agent_name]["initial"]}
            final_kw = {k[0]: k[1] for k in agent_keywords[agent_name]["final"]}
            
            # New concepts introduced
            new_concepts = [k for k in final_kw if k not in initial_kw]
            if new_concepts:
                visualization += "- New concepts introduced: " + ", ".join(new_concepts) + "\n"
            
            # Concepts no longer emphasized
            dropped_concepts = [k for k in initial_kw if k not in final_kw]
            if dropped_concepts:
                visualization += "- Concepts no longer emphasized: " + ", ".join(dropped_concepts) + "\n"
            
            # Concepts that persisted
            persistent_concepts = [k for k in initial_kw if k in final_kw]
            if persistent_concepts:
                visualization += "- Persistent themes: " + ", ".join(persistent_concepts) + "\n"
        
        visualization += "\n---\n\n"
    
    # Generate cross-cutting themes section
    visualization += """
## Cross-Cutting Themes

The following themes emerged and evolved throughout the debate:
"""
    
    # Analyze all the keywords across agents to identify common themes
    all_keywords = []
    for agent, phases in agent_keywords.items():
        for phase, keywords in phases.items():
            all_keywords.extend([k[0] for k in keywords])
    
    # Count frequencies of all keywords
    keyword_counter = Counter(all_keywords)
    most_common = keyword_counter.most_common(10)
    
    # List the top themes
    for i, (keyword, count) in enumerate(most_common, 1):
        visualization += f"{i}. **{keyword}** (mentioned {count} times)\n"
    
    # Add Mermaid diagram reference
    visualization += """
## Debate Flow Visualization

The following Mermaid diagram shows the flow of the debate and how concepts evolved:

```mermaid
graph TD
    Problem[Problem Statement] --> Perspectives[Initial Perspectives]
    Perspectives --> Critiques[Critiques] 
    Critiques --> Responses[Responses]
    Responses --> CommonGround[Common Ground]
    CommonGround --> FinalPositions[Final Positions]
```

## Sentiment Evolution Chart

The following chart shows how sentiment evolved for each agent throughout the debate phases:

| Agent | Initial | After Critiques | After Response | Final | Net Change |
|-------|---------|-----------------|----------------|-------|------------|
"""
    
    # Add sentiment data for each agent
    for agent, sentiments in agent_sentiments.items():
        initial = sentiments.get("initial", 0)
        critiques = sentiments.get("critiques", "N/A")
        response = sentiments.get("response", "N/A")
        final = sentiments.get("final", 0)
        
        if isinstance(critiques, float):
            critiques = f"{critiques:.2f}"
        if isinstance(response, float):
            response = f"{response:.2f}"
            
        change = final - initial
        change_text = f"{change:.2f}"
        
        visualization += f"| {agent} | {initial:.2f} | {critiques} | {response} | {final:.2f} | {change_text} |\n"
    
    # Add external knowledge references used
    if hasattr(client, 'knowledge_references') and client.knowledge_references:
        visualization += "\n## External Knowledge References\n\n"
        visualization += "The following external sources were referenced during the debate:\n\n"
        
        for i, ref in enumerate(client.knowledge_references, 1):
            query = ref.get('query', 'Unknown query')
            source = ref.get('source', 'Unknown source')
            agent = ref.get('agent', 'Unknown agent')
            phase = ref.get('phase', 'Unknown phase')
            
            visualization += f"{i}. **{query}** (by {agent} in {phase})\n"
            visualization += f"   {source}\n\n"
    
    return visualization

def run_semi_agentic_debate(problem_statement, agents, output_dir=None, knowledge_config=None):
    """
    Run a debate with semi-agentic properties, balancing reliability with agent autonomy.
    
    This approach:
    1. Uses a simulated moderator to guide the process
    2. Allows agents to select their critique targets 
    3. Enables agents to decide which critiques to respond to
    4. Preserves structured phases and reliable execution
    5. Generates advanced visualizations of idea evolution
    6. Integrates external knowledge sources when available
    
    Args:
        problem_statement (str): The topic for debate
        agents (list): List of agent objects
        output_dir (str, optional): Directory to save results
        knowledge_config (dict, optional): Configuration for knowledge integration
    """
    # Load API key and create client
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Initialize knowledge integration if configured
    knowledge_integration = None
    if knowledge_config:
        logging.info(f"Initializing knowledge integration with config: {knowledge_config}")
        knowledge_integration = KnowledgeIntegration(knowledge_config, client)
        # Attach a list to track knowledge references
        client.knowledge_references = []
        logging.info("Knowledge integration initialized successfully")
        
        # If no document directory or empty directory, log a message about fallbacks
        doc_dir = knowledge_config.get("document_dir", "documents")
        if not os.path.exists(doc_dir) or not os.listdir(doc_dir):
            logging.info("No documents found in directory. Will use web search and AI generation as fallbacks.")
    
    # Create output directory
    if output_dir is None:
        timestamp = int(time.time())
        output_dir = f"output_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create moderator with knowledge integration
    moderator = ModeratorAgent(problem_statement, knowledge_integration)
    
    # Initialize results
    results = {
        "problem_statement": problem_statement,
        "agents": [agent.name for agent in agents],
        "moderator_messages": {},
        "phases": {},
        "knowledge_references": [] # To track external sources used
    }
    
    # Welcome message from moderator
    welcome_prompt = f"Introduce the debate on '{problem_statement}'. Explain that we'll be exploring this topic in a structured format with experts from different domains. If relevant, use [REF: {problem_statement}] to gather background information. Keep it concise but welcoming."
    welcome_message = moderator.generate_message(client, welcome_prompt, "welcome")
    results["moderator_messages"]["welcome"] = welcome_message
    
    print(f"\n🎭 Moderator: {welcome_message}\n")
    
    # PHASE 1: Initial Perspectives
    # Moderator introduces the first phase
    phase1_intro_prompt = "Introduce the first phase of the debate where each expert will provide their initial perspective. Invite them to share concise viewpoints based on their expertise."
    phase1_intro = moderator.generate_message(client, phase1_intro_prompt, "phase1_intro")
    results["moderator_messages"]["phase1_intro"] = phase1_intro
    
    print(f"\n🎭 Moderator: {phase1_intro}\n")
    print("1️⃣ PHASE 1: Initial Perspectives")
    
    # Enhance agent system messages with knowledge retrieval capability
    reference_instruction = "\n\nYou can request external information by using [REF: your query] in your response. For example: 'Studies have shown [REF: latest research on AI-generated content reliability]'"

    for agent in agents:
        if knowledge_integration:
            # Use a temporary variable instead of trying to modify the property directly
            updated_message = agent.system_message + reference_instruction
            
            # For autogen agents, we can update the llm_config's system_message
            if hasattr(agent, 'llm_config') and isinstance(agent.llm_config, dict):
                agent.llm_config['system_message'] = updated_message
                logger.info(f"Updated system message for {agent.name} via llm_config")
            # Alternatively, some agents might have an update_system_message method
            elif hasattr(agent, 'update_system_message') and callable(getattr(agent, 'update_system_message')):
                agent.update_system_message(updated_message)
                logger.info(f"Updated system message for {agent.name} via update method")
            else:
                logger.warning(f"Could not update system message for {agent.name}. Knowledge integration instructions not added.")    
    # Collect perspectives from each agent
    perspectives = {}
    
    for agent in agents:
        print(f"  💬 {agent.name} is sharing perspective...")
        
        # Check if the agent has a generate_argument method
        if hasattr(agent, 'generate_argument') and callable(getattr(agent, 'generate_argument')):
            try:
                print(f"  🧠 {agent.name} is generating argument with knowledge integration...")
                perspective = agent.generate_argument(problem_statement)
                logger.info(f"{agent.name} generated argument using custom method")
            except Exception as e:
                logger.error(f"Error in generate_argument for {agent.name}: {str(e)}")
                # Fall back to standard method
                perspective = generate_standard_perspective(agent, client, problem_statement, knowledge_integration)
        else:
            # Use standard perspective generation
            perspective = generate_standard_perspective(agent, client, problem_statement, knowledge_integration)
        
        perspectives[agent.name] = perspective
        print(f"  ✅ {agent.name}: {perspective[:70]}...")
    
    # Store Phase 1 results
    results["phases"]["initial_perspectives"] = perspectives
    
    # Moderator summarizes initial perspectives
    perspectives_text = "\n\n".join([f"{name}: {content}" for name, content in perspectives.items()])
    phase1_summary_prompt = "Summarize the key points from each expert's initial perspective. Highlight areas of agreement, disagreement, and unique insights. You can reference external research if helpful with [REF: relevant query]. Then, transition to the critique phase where experts will provide constructive feedback on each other's perspectives."
    phase1_summary = moderator.generate_message(client, phase1_summary_prompt, "phase1_summary", perspectives_text)
    results["moderator_messages"]["phase1_summary"] = phase1_summary
    
    print(f"\n🎭 Moderator: {phase1_summary}\n")
    
    # PHASE 2: Critiques - with agent autonomy in choosing whom to critique
    print("2️⃣ PHASE 2: Critiques")
    critiques = {}
    
    # Ask agents to decide whom to critique
    for agent in agents:
        print(f"  💬 {agent.name} is selecting a perspective to critique...")
        
        # First, let the agent decide whom to critique
        target_selection_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": agent.system_message},
                {"role": "user", "content": f"""
                Here are the perspectives on '{problem_statement}':
                
                {perspectives_text}
                
                Based on your expertise and thinking style, which other expert's perspective would you 
                most want to critique or provide constructive feedback on? Choose ONE expert and explain 
                briefly why you selected them (in 1-2 sentences).
                
                Format your response as: "I choose to critique [EXPERT NAME] because [brief reason]"
                """}
            ],
            max_tokens=100
        )
        
        target_selection = target_selection_response.choices[0].message.content
        
        # Parse the target from the response
        target_name = None
        for other_agent in agents:
            if other_agent.name != agent.name and other_agent.name in target_selection:
                target_name = other_agent.name
                break
        # Fallback if parsing failed
        if not target_name:
            # Choose first agent that's not self
            for other_agent in agents:
                if other_agent.name != agent.name:
                    target_name = other_agent.name
                    break
        
        print(f"  📌 {agent.name} chose to critique {target_name}")
        
        # Now generate the actual critique
        critique_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": agent.system_message},
                {"role": "user", "content": f"""
                You've decided to critique {target_name}'s perspective on '{problem_statement}':
                
                {perspectives[target_name]}
                
                You can reference external information using [REF: your query] to support your critique.
                Provide a constructive critique based on your expertise. Identify potential limitations,
                oversights, or areas that could be strengthened. Be specific and constructive.
                
                Start with addressing {target_name} directly and keep your critique under 150 words.
                """}
            ],
            max_tokens=300
        )
        
        critique = critique_response.choices[0].message.content
        
        # Process any reference requests
        if knowledge_integration:
            critique = process_reference_requests(
                critique, 
                knowledge_integration, 
                agent_name=agent.name, 
                phase="critique"
            )
            
            # Ensure there's a knowledge reference
            if "[REF:" not in critique and "[Reference for" not in critique:
                critique = ensure_knowledge_in_agent_message(
                    critique, 
                    agent.name, 
                    knowledge_integration, 
                    "critique", 
                    problem_statement
                )
            
        if agent.name not in critiques:
            critiques[agent.name] = {}
        critiques[agent.name][target_name] = critique
        print(f"  ✅ {agent.name} critiqued {target_name}")
    
    # Store Phase 2 results
    results["phases"]["critiques"] = critiques
    
    # Moderator summarizes critiques
    critiques_text = ""
    for critic_name, targets in critiques.items():
        for target_name, critique in targets.items():
            critiques_text += f"{critic_name} to {target_name}:\n{critique}\n\n"
    
    phase2_summary_prompt = "Summarize the key critiques provided by the experts. Highlight patterns, tensions, and areas where experts challenged each other's thinking. Then, transition to the response phase where experts will address the critiques directed at them."
    phase2_summary = moderator.generate_message(client, phase2_summary_prompt, "phase2_summary", critiques_text)
    results["moderator_messages"]["phase2_summary"] = phase2_summary
    
    print(f"\n🎭 Moderator: {phase2_summary}\n")
    
    # PHASE 3: Responses to Critiques - with agent autonomy in crafting responses
    print("3️⃣ PHASE 3: Responses to Critiques")
    responses = {}
    
    # Identify which agents received critiques
    critique_targets = {}
    for critic_name, targets in critiques.items():
        for target_name, critique in targets.items():
            if target_name not in critique_targets:
                critique_targets[target_name] = []
            critique_targets[target_name].append({"critic": critic_name, "critique": critique})
    
    # Have agents respond to their critiques
    for agent in agents:
        if agent.name in critique_targets:
            received_critiques = critique_targets[agent.name]
            critiques_received_text = "\n\n".join([f"From {c['critic']}:\n{c['critique']}" for c in received_critiques])
            
            print(f"  💬 {agent.name} is responding to critiques...")
            
            response_message = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": agent.system_message},
                    {"role": "user", "content": f"""
                    You've received the following critiques of your perspective on '{problem_statement}':
                    
                    {critiques_received_text}
                    
                    You can reference external information using [REF: your query] to support your response.
                    Respond to these critiques. Acknowledge valid points and defend or refine your 
                    position where appropriate. Be thoughtful and constructive in your response.
                    
                    Keep your response under 150 words.
                    """}
                ],
                max_tokens=300
            )
            
            response = response_message.choices[0].message.content
            
            # Process any reference requests
            if knowledge_integration:
                response = process_reference_requests(
                    response, 
                    knowledge_integration, 
                    agent_name=agent.name, 
                    phase="response"
                )
                
                # Ensure there's a knowledge reference
                if "[REF:" not in response and "[Reference for" not in response:
                    response = ensure_knowledge_in_agent_message(
                        response, 
                        agent.name, 
                        knowledge_integration, 
                        "response", 
                        problem_statement
                    )
                
            responses[agent.name] = {
                "critiques_received": [c["critic"] for c in received_critiques],
                "response": response
            }
            print(f"  ✅ {agent.name} responded to critiques")
        else:
            # For agents who didn't receive direct critiques
            response_message = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": agent.system_message},
                    {"role": "user", "content": f"""
                    You haven't received direct critiques of your perspective on '{problem_statement}', 
                    but you've observed the critiques exchanged between others.
                    
                    You can reference external information using [REF: your query] if helpful.
                    Provide a brief response that reflects on how the critiques you've observed might 
                    apply to or affect your own thinking on the problem.
                    
                    Keep your response under 120 words.
                    """}
                ],
                max_tokens=250
            )
            
            response = response_message.choices[0].message.content
            
            # Process any reference requests
            if knowledge_integration:
                response = process_reference_requests(
                    response, 
                    knowledge_integration, 
                    agent_name=agent.name, 
                    phase="response"
                )
                
                # Ensure there's a knowledge reference
                if "[REF:" not in response and "[Reference for" not in response:
                    response = ensure_knowledge_in_agent_message(
                        response, 
                        agent.name, 
                        knowledge_integration, 
                        "response", 
                        problem_statement
                    )
                
            responses[agent.name] = {
                "critiques_received": [],
                "response": response
            }
            print(f"  ✅ {agent.name} provided general reflections")
    
    # Store Phase 3 results
    results["phases"]["responses"] = responses
    
    # Moderator summarizes responses
    responses_text = "\n\n".join([f"{name}:\n{data['response']}" for name, data in responses.items()])
    
    phase3_summary_prompt = "Summarize how the experts have responded to critiques. Highlight how positions have evolved or been refined. Then, transition to the common ground phase where experts will identify areas of consensus and potential for integration."
    phase3_summary = moderator.generate_message(client, phase3_summary_prompt, "phase3_summary", responses_text)
    results["moderator_messages"]["phase3_summary"] = phase3_summary
    
    print(f"\n🎭 Moderator: {phase3_summary}\n")
    
    # PHASE 4: Common Ground - let agents independently identify common ground
    print("4️⃣ PHASE 4: Finding Common Ground")
    common_ground = {}
    
    # Compile debate context so far
    debate_context = f"""
    PROBLEM: '{problem_statement}'
    
    INITIAL PERSPECTIVES:
    {perspectives_text}
    
    CRITIQUES:
    {critiques_text}
    
    RESPONSES:
    {responses_text}
    """
    
    # Let each agent identify common ground
    for agent in agents:
        print(f"  💬 {agent.name} is identifying common ground...")
        
        common_ground_message = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": agent.system_message},
                {"role": "user", "content": f"""
                Review the debate so far:
                
                {debate_context}
                
                Based on your expertise and the discussion, identify:
                1. Key points of common ground across the different perspectives
                2. How these different viewpoints might be integrated into a stronger approach
                
                You can reference external information using [REF: your query] if it helps identify integration opportunities.
                Structure your response clearly and keep it under 180 words.
                """}
            ],
            max_tokens=350
        )
        
        common_ground_text = common_ground_message.choices[0].message.content
        
        # Process any reference requests
        if knowledge_integration:
            common_ground_text = process_reference_requests(
                common_ground_text, 
                knowledge_integration, 
                agent_name=agent.name, 
                phase="common_ground"
            )
            
            # Ensure there's a knowledge reference
            if "[REF:" not in common_ground_text and "[Reference for" not in common_ground_text:
                common_ground_text = ensure_knowledge_in_agent_message(
                    common_ground_text, 
                    agent.name, 
                    knowledge_integration, 
                    "common_ground", 
                    problem_statement
                )
            
        common_ground[agent.name] = common_ground_text
        print(f"  ✅ {agent.name} identified common ground")
    
    # Store Phase 4 results
    results["phases"]["common_ground"] = common_ground
    
    # Moderator synthesizes common ground
    common_ground_text = "\n\n".join([f"{name}:\n{content}" for name, content in common_ground.items()])
    
    phase4_summary_prompt = "Synthesize the common ground identified by the experts. Highlight key areas of consensus and how different perspectives might complement each other. Then, transition to the final phase where experts will provide their concluding thoughts and recommendations."
    phase4_summary = moderator.generate_message(client, phase4_summary_prompt, "phase4_summary", common_ground_text)
    results["moderator_messages"]["phase4_summary"] = phase4_summary
    
    print(f"\n🎭 Moderator: {phase4_summary}\n")
    
    # PHASE 5: Final Positions - with evolved thinking
    print("5️⃣ PHASE 5: Final Positions")
    final_positions = {}
    
    # Updated debate context
    debate_context += f"""
    COMMON GROUND:
    {common_ground_text}
    
    MODERATOR SYNTHESIS:
    {phase4_summary}
    """
    
    # Get final positions from each agent
    for agent in agents:
        print(f"  💬 {agent.name} is formulating final position...")
        
        # Extract initial perspective for reference
        initial_perspective = perspectives[agent.name]
        
        final_position_message = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": agent.system_message},
                {"role": "user", "content": f"""
                The debate on '{problem_statement}' is concluding. 
                
                Your initial perspective was:
                {initial_perspective}
                
                Since then, you've engaged in critiques, responses, and finding common ground.
                
                You can reference external information using [REF: your query] to help support your final position.
                Provide your final position and recommendations:
                
                1. Begin with "Final Position:" followed by your main stance
                2. List 2-3 key recommendations based on the entire debate
                3. Explain how your thinking has evolved from your initial perspective
                
                Keep your response under 180 words.
                """}
            ],
            max_tokens=350
        )
        
        final_position = final_position_message.choices[0].message.content
        
        # Process any reference requests
        if knowledge_integration:
            final_position = process_reference_requests(
                final_position, 
                knowledge_integration, 
                agent_name=agent.name, 
                phase="final_position"
            )
            
            # Ensure there's a knowledge reference
            if "[REF:" not in final_position and "[Reference for" not in final_position:
                final_position = ensure_knowledge_in_agent_message(
                    final_position, 
                    agent.name, 
                    knowledge_integration, 
                    "final_position", 
                    problem_statement
                )
            
        final_positions[agent.name] = final_position
        print(f"  ✅ {agent.name} provided final position")
    
    # Store Phase 5 results
    results["phases"]["final_positions"] = final_positions
    
    # Moderator concludes the debate
    final_positions_text = "\n\n".join([f"{name}:\n{position}" for name, position in final_positions.items()])
    
    conclusion_prompt = "Conclude the debate by summarizing the journey from initial perspectives to final positions. Highlight how thinking evolved and identify key insights that emerged. Thank the experts for their contributions."
    conclusion = moderator.generate_message(client, conclusion_prompt, "conclusion", final_positions_text)
    results["moderator_messages"]["conclusion"] = conclusion
    
    print(f"\n🎭 Moderator: {conclusion}\n")
    
    # If knowledge integration was used, store references
    if knowledge_integration and hasattr(client, 'knowledge_references'):
        results["knowledge_references"] = client.knowledge_references
    
    # FINAL REPORT GENERATION
    print("6️⃣ Generating Final Report")
    
    # Let the moderator create the final report
    final_report_prompt = f"""
    Generate a comprehensive final report on the debate about '{problem_statement}'.
    
    The report should include:
    1. Executive Summary (2-3 sentences)
    2. Key Perspectives (summarize each agent's main points)
    3. Evolution of Ideas (how perspectives changed through debate)
    4. Areas of Agreement and Disagreement
    5. Integrated Solution (combining the best ideas)
    6. Implementation Considerations
    7. Recommendations for Further Research
    
    Use markdown formatting for better readability.
    """
    
    full_debate_context = f"""
    PROBLEM STATEMENT: {problem_statement}
    
    INITIAL PERSPECTIVES:
    {perspectives_text}
    
    CRITIQUES:
    {critiques_text}
    
    RESPONSES:
    {responses_text}
    
    COMMON GROUND:
    {common_ground_text}
    
    FINAL POSITIONS:
    {final_positions_text}
    
    MODERATOR SUMMARIES:
    - After Initial Perspectives: {results["moderator_messages"]["phase1_summary"]}
    - After Critiques: {results["moderator_messages"]["phase2_summary"]}
    - After Responses: {results["moderator_messages"]["phase3_summary"]}
    - After Common Ground: {results["moderator_messages"]["phase4_summary"]}
    """
    
    final_report_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": moderator.system_message},
            {"role": "user", "content": f"{full_debate_context}\n\n{final_report_prompt}"}
        ],
        max_tokens=1800
    )
    
    final_report = final_report_response.choices[0].message.content
    
    # Process any reference requests in the final report
    if knowledge_integration:
        final_report = process_reference_requests(
            final_report, 
            knowledge_integration, 
            agent_name="Moderator", 
            phase="final_report"
        )
        
    results["final_report"] = final_report
    print("  ✅ Final report generated")
    
    # Save results
    report_path = os.path.join(output_dir, "debate_summary.md")
    with open(report_path, "w") as f:
        f.write("# Debate Summary\n\n")
        f.write(final_report)
    
    # Generate enhanced idea evolution visualization
    print("  📊 Generating enhanced idea evolution visualizations...")
    
    # Text-based visualization
    visualization = generate_idea_evolution_visualization(
        perspectives, critiques, responses, common_ground, final_positions, client
    )
    visualization_path = os.path.join(output_dir, "idea_evolution.md")
    with open(visualization_path, "w") as f:
        f.write("# Evolution of Ideas Throughout the Debate\n\n")
        f.write(visualization)
    results["idea_evolution"] = visualization
    
    # Generate Mermaid diagram
    mermaid_diagram = generate_mermaid_diagram(results)
    mermaid_path = os.path.join(output_dir, "debate_flow.md")
    with open(mermaid_path, "w") as f:
        f.write("# Debate Flow Diagram\n\n")
        f.write("```mermaid\n")
        f.write(mermaid_diagram)
        f.write("\n```")
    results["mermaid_diagram"] = mermaid_diagram
    
    # Generate network graph
    try:
        graph_path = generate_idea_graphs(results, output_dir)
        print(f"  ✅ Generated network graph: {graph_path}")
        results["graph_path"] = graph_path
    except Exception as e:
        print(f"  ⚠️ Could not generate graph: {str(e)}")
    
    # If knowledge integration was used, create references summary
    if knowledge_integration and hasattr(client, 'knowledge_references') and client.knowledge_references:
        references_path = os.path.join(output_dir, "knowledge_references.md")
        with open(references_path, "w") as f:
            f.write("# External Knowledge References\n\n")
            f.write("The following external sources were referenced during the debate:\n\n")
            
            for i, ref in enumerate(client.knowledge_references, 1):
                source_type = ref.get('source_type', 'Unknown')
                query = ref.get('query', 'Unknown query')
                source = ref.get('source', 'Unknown source')
                agent = ref.get('agent', 'Unknown agent')
                phase = ref.get('phase', 'Unknown phase')
                
                f.write(f"{i}. **Query:** {query}\n")
                if source_type:
                    f.write(f"   **Type:** {source_type}\n")
                f.write(f"   **Source:** {source}\n")
                f.write(f"   **Used by:** {agent}\n")
                f.write(f"   **Phase:** {phase}\n\n")
        
        print(f"  ✅ Generated external knowledge references summary: {references_path}")
            
    # Save full debate data
    data_path = os.path.join(output_dir, "debate_data.json")
    with open(data_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Debate completed successfully!")
    print(f"Results saved to: {output_dir}")
    print(f"- Full report: {report_path}")
    print(f"- Idea evolution visualization: {visualization_path}")
    print(f"- Debate flow diagram: {mermaid_path}")
    print(f"- Complete debate data: {data_path}")
    
    return output_dir, results