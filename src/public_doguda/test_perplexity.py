import asyncio
from public_doguda.perplexity_to_markdown import perplexity_to_markdown

async def test_perplexity():
    url = "https://www.perplexity.ai/search/1d9a5846-0b46-45ff-8943-66dc97f0d1d6"
    print(f"Testing Perplexity to Markdown with URL: {url}")
    
    try:
        response = await perplexity_to_markdown(url)
        
        print("\n--- Markdown Output ---")
        if response.markdown:
            print(response.markdown[:500] + "..." if len(response.markdown) > 500 else response.markdown)
            print(f"\nTotal characters: {len(response.markdown)}")
        else:
            print("Failed to extract markdown content.")
            
        if response.raw_html:
            print(f"Raw HTML captured: {len(response.raw_html)} bytes")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_perplexity())
