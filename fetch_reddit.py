import praw
import os
import json
from dotenv import load_dotenv

load_dotenv()

def fetch_top_posts(subreddits, post_limit=10, comment_limit=10):
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT")
    )
    
    data = []
    
    for sub_name in subreddits:
        sub_name = sub_name.strip() # Clean up any spaces
        if not sub_name: continue
        
        print(f"Fetching /r/{sub_name}...")
        try:
            subreddit = reddit.subreddit(sub_name)
            for post in subreddit.top(time_filter="day", limit=post_limit):
                post_data = {
                    "subreddit": sub_name,
                    "title": post.title,
                    "author": str(post.author),
                    "score": post.score,
                    "content": post.selftext[:2000], 
                    "comments": []
                }
                
                post.comments.replace_more(limit=0)
                for comment in post.comments[:comment_limit]:
                    post_data["comments"].append({
                        "body": comment.body[:500],
                        "score": comment.score
                    })
                data.append(post_data)
        except Exception as e:
            print(f"Error fetching {sub_name}: {e}")
            
    return data

if __name__ == "__main__":
    # Get subreddits from .env, split by comma
    subs_string = os.getenv("REDDIT_SUBREDDITS", "localLLaMA,ClaudeAI,singularity,ArtificialInteligence")
    subs_list = subs_string.split(",")
    
    results = fetch_top_posts(subs_list)
    
    with open("reddit_today.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"Successfully saved {len(results)} posts from {len(subs_list)} subreddits to reddit_today.json")
