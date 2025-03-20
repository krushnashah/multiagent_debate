import os
import json
import requests
import logging
from dotenv import load_dotenv 
import re
from openai import OpenAI
import time

# Try to import PDF and DOCX libraries, but handle if not available
try:
    from PyPDF2 import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logging.warning("PyPDF2 not installed. PDF support disabled.")

try:
    import docx
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False
    logging.warning("python-docx not installed. DOCX support disabled.")

# Load environment variables
load_dotenv()

DOCUMENT_DIR = os.getenv("DOCUMENT_DIR", "documents")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("KnowledgeIntegration")

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    if not PDF_SUPPORT:
        logger.warning("PDF support is disabled. Install PyPDF2 to enable.")
        return ""
        
    try:
        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}")
        return ""

def extract_text_from_docx(docx_path):
    """Extract text from a DOCX file."""
    if not DOCX_SUPPORT:
        logger.warning("DOCX support is disabled. Install python-docx to enable.")
        return ""
        
    try:
        doc = docx.Document(docx_path)
        return "\n".join(para.text for para in doc.paragraphs)
    except Exception as e:
        logger.error(f"Error reading DOCX {docx_path}: {e}")
        return ""

def extract_text_from_txt(txt_path):
    """Extract text from a plain text file."""
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # Try again with different encoding
        try:
            with open(txt_path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading TXT {txt_path}: {e}")
            return ""
    except Exception as e:
        logger.error(f"Error reading TXT {txt_path}: {e}")
        return ""

def search_local_documents(query):
    """Search local PDFs, DOCX, and TXT files for relevant content."""
    if not os.path.exists(DOCUMENT_DIR):
        logger.warning(f"Document directory '{DOCUMENT_DIR}' not found. Skipping local search.")
        return None
        
    # Check if directory is empty
    files = os.listdir(DOCUMENT_DIR)
    if not files:
        logger.warning(f"Document directory '{DOCUMENT_DIR}' is empty. Skipping local search.")
        return None

    results = []
    for filename in files:
        file_path = os.path.join(DOCUMENT_DIR, filename)
        if not os.path.isfile(file_path):
            continue
            
        text = ""
        if filename.lower().endswith(".pdf") and PDF_SUPPORT:
            text = extract_text_from_pdf(file_path)
        elif filename.lower().endswith(".docx") and DOCX_SUPPORT:
            text = extract_text_from_docx(file_path)
        elif filename.lower().endswith(".txt"):
            text = extract_text_from_txt(file_path)
        else:
            continue
            
        # Simple keyword search
        if query.lower() in text.lower():
            # Find a relevant snippet
            query_pos = text.lower().find(query.lower())
            start = max(0, query_pos - 100)
            end = min(len(text), query_pos + 300)
            snippet = text[start:end].replace("\n", " ").strip()
            
            results.append(f"📄 {filename}: {snippet}...")

    if results:
        logger.info(f"Local knowledge found for '{query}'. Found {len(results)} matches.")
    else:
        logger.info(f"No local knowledge found for '{query}'.")

    return results if results else None

def search_web(query):
    """Search the web using Google Custom Search API."""
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        logger.warning("Google API key or CSE ID is missing. Web search cannot be performed.")
        return None

    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CX}"
    
    try:
        response = requests.get(url)
        data = response.json()

        results = data.get("items", [])
        if not results:
            logger.info(f"No relevant web results found for '{query}'.")
            return None

        formatted_results = []
        for res in results[:5]:  # Limit to top 5 results
            title = res.get('title', 'Unknown Title')
            link = res.get('link', '#')
            snippet = res.get('snippet', 'No description available')
            formatted_results.append(f"🌐 {title}: {snippet} [Source: {link}]")

        logger.info(f"Web search results retrieved for '{query}'. Found {len(formatted_results)} results.")
        return formatted_results

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return None

def generate_knowledge(query, client=None):
    """Generate knowledge using OpenAI API when no other sources are available."""
    # Create a client if none was provided
    if not client:
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key is missing. Cannot generate knowledge.")
            return None
            
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            return None
    
    try:
        logger.info(f"Generating knowledge for '{query}' using OpenAI API")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": 
                 "You are a knowledge base that provides factual, concise information. " +
                 "When asked about a topic, provide 3-5 key points that would be helpful " +
                 "for a debate or discussion. Focus on current understanding, trends, and " +
                 "important considerations. Format as bullet points."
                },
                {"role": "user", "content": f"Provide current knowledge about: {query}"}
            ],
            max_tokens=500
        )
        
        generated_content = response.choices[0].message.content
        
        # Format the result
        result = f"🤖 AI-Generated Knowledge: {generated_content}"
        
        logger.info(f"Successfully generated knowledge for '{query}'")
        return [result]
        
    except Exception as e:
        logger.error(f"Error generating knowledge: {e}")
        return None

class KnowledgeIntegration:
    """Class to handle knowledge integration from various sources."""
    
    def __init__(self, config=None, client=None):
        """
        Initialize the knowledge integration system.
        
        Args:
            config (dict): Configuration options
            client: OpenAI client instance to track references
        """
        self.config = config or {}
        self.client = client
        self.document_dir = self.config.get("document_dir", DOCUMENT_DIR)
        self.use_web_search = self.config.get("use_web_search", True)
        self.use_ai_generation = self.config.get("use_ai_generation", True)
        
        # Set document directory in environment if specified in config
        if "document_dir" in self.config:
            os.environ["DOCUMENT_DIR"] = self.config["document_dir"]
        
        # Initialize a list to track references if client doesn't have one
        if self.client and not hasattr(self.client, 'knowledge_references'):
            self.client.knowledge_references = []
            
        logger.info(f"Knowledge Integration initialized with: document_dir={self.document_dir}, " +
                    f"use_web_search={self.use_web_search}, use_ai_generation={self.use_ai_generation}")
        
        # Check if document directory exists and has files
        self._check_document_directory()
    
    def _check_document_directory(self):
        """Check if document directory exists and contains files."""
        if not os.path.exists(self.document_dir):
            logger.warning(f"Document directory '{self.document_dir}' not found.")
            return False
            
        files = [f for f in os.listdir(self.document_dir) 
                if os.path.isfile(os.path.join(self.document_dir, f)) and 
                f.lower().endswith(('.pdf', '.docx', '.txt'))]
                
        if not files:
            logger.warning(f"No document files (.pdf, .docx, .txt) found in '{self.document_dir}'.")
            return False
            
        logger.info(f"Found {len(files)} document files in '{self.document_dir}'.")
        return True
    
    def retrieve_knowledge(self, query):
        """
        Retrieve knowledge based on the query, with fallbacks.
        
        Args:
            query (str): The search query
            
        Returns:
            list: List of knowledge results or None
        """
        logger.info(f"Knowledge request: '{query}'")
        
        # Record start time for performance tracking
        start_time = time.time()
        
        # Try local documents first
        local_results = search_local_documents(query)
        if local_results:
            logger.info(f"Found {len(local_results)} local document results in {time.time() - start_time:.2f}s")
            
            # Track the reference
            self._track_reference(query, "Local Document", local_results[0])
            
            return local_results
        
        # Fall back to web search if enabled
        if self.use_web_search:
            logger.info("No local results, trying web search")
            web_results = search_web(query)
            if web_results:
                logger.info(f"Found {len(web_results)} web results in {time.time() - start_time:.2f}s")
                
                # Track the reference
                self._track_reference(query, "Web Search", web_results[0])
                
                return web_results
                
            logger.warning("Web search returned no results")
        
        # Fall back to AI generation if enabled
        if self.use_ai_generation:
            logger.info("No local or web results, generating knowledge with AI")
            generated_results = generate_knowledge(query, self.client)
            if generated_results:
                logger.info(f"Generated AI knowledge in {time.time() - start_time:.2f}s")
                
                # Track the reference
                self._track_reference(query, "AI Generated", generated_results[0])
                
                return generated_results
                
            logger.warning("AI generation failed")
        
        logger.warning(f"No knowledge found for '{query}' after trying all sources")
        return None
    
    def _track_reference(self, query, source_type, content):
        """Track a reference for documentation."""
        if not self.client or not hasattr(self.client, 'knowledge_references'):
            return
            
        # Truncate content for storage
        content_preview = content[:200] + "..." if len(content) > 200 else content
        
        self.client.knowledge_references.append({
            "query": query,
            "source_type": source_type,
            "source": content_preview,
            "timestamp": time.time()
        })

def process_reference_requests(text, knowledge_integration, agent_name="unknown", phase="unknown"):
    """
    Process reference requests in the format [REF: query] and replace them with information.
    Also track references for documentation.
    
    Args:
        text (str): Text potentially containing reference requests
        knowledge_integration (KnowledgeIntegration): Knowledge integration instance
        agent_name (str): Name of the agent making the request
        phase (str): Current phase of the debate
        
    Returns:
        str: Text with reference requests replaced with actual information
    """
    # Pattern to match reference requests
    pattern = r'\[REF:(.*?)\]'
    matches = re.findall(pattern, text)
    
    if not matches:
        return text
    
    logger.info(f"Found {len(matches)} reference requests in text from {agent_name}")
    
    for query in matches:
        query = query.strip()
        logger.info(f"Processing reference request: '{query}'")
        
        # Get information from knowledge base
        results = knowledge_integration.retrieve_knowledge(query)
        
        if results:
            # Format the reference information
            reference_text = f"[Reference for '{query}': "
            reference_text += results[0]
            if len(results) > 1:
                reference_text += f" (+ {len(results)-1} more references)"
            reference_text += "]"
            
            # Replace the reference request with the information
            text = text.replace(f"[REF:{query}]", reference_text)
            
            # Track this reference for later documentation
            if hasattr(knowledge_integration, 'client') and hasattr(knowledge_integration.client, 'knowledge_references'):
                knowledge_integration.client.knowledge_references.append({
                    "query": query,
                    "source": results[0][:200] + "..." if len(results[0]) > 200 else results[0],
                    "agent": agent_name,
                    "phase": phase
                })
            
            logger.info(f"Successfully replaced reference with information")
        else:
            # Replace with AI-generated knowledge as a last resort
            ai_knowledge = generate_knowledge(query, knowledge_integration.client)
            
            if ai_knowledge:
                reference_text = f"[AI-generated knowledge for '{query}': {ai_knowledge[0]}]"
                text = text.replace(f"[REF:{query}]", reference_text)
                
                # Track this reference
                if hasattr(knowledge_integration, 'client') and hasattr(knowledge_integration.client, 'knowledge_references'):
                    knowledge_integration.client.knowledge_references.append({
                        "query": query,
                        "source": "AI-generated: " + ai_knowledge[0][:150] + "...",
                        "agent": agent_name,
                        "phase": phase
                    })
                    
                logger.info(f"Used AI-generated knowledge as fallback")
            else:
                # If all else fails, just remove the reference request
                text = text.replace(f"[REF:{query}]", f"[No reference information found for '{query}']")
                logger.warning(f"No reference information found for '{query}'")
    
    return text

# Function to retrieve knowledge (used by agents)
def retrieve_knowledge(query):
    """
    Simplified function to retrieve knowledge based on a query.
    This is used directly by agents that don't have access to the KnowledgeIntegration instance.
    
    Args:
        query (str): The search query
        
    Returns:
        list: List of knowledge results or None
    """
    # Try local documents
    local_results = search_local_documents(query)
    if local_results:
        return local_results
    
    # Try web search
    web_results = search_web(query)
    if web_results:
        return web_results
    
    # Try AI generation as a last resort
    return generate_knowledge(query)