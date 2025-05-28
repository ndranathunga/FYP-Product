import re
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
import uuid
from loguru import logger
from datetime import datetime, timedelta, timezone
import random
import ast
import json

# Your existing DB schemas and functions
from backend.app.db import schemas as db_schemas
from backend.app.db import products as db_products
from backend.app.db import reviews as db_reviews
from backend.app.db import analysis_results as db_analysis_results

# Your analysis service for triggering analysis (optional for seeding)
from backend.app.services.analysis_service import (
    get_analysis_service_instance,
    AnalysisService,
)

# (You might need a way to bypass normal auth for this admin endpoint,
# or use a specific admin user/key if you have one. For simplicity now, no auth.)

router = APIRouter(prefix="/admin-seed", tags=["Admin Seed Data"])


# --- Date Helper ---
def get_varied_past_timestamps(count: int, days_spread: int = 90) -> List[datetime]:
    timestamps = []
    now = datetime.now(timezone.utc)
    for i in range(count):
        days_ago = random.randint(1, days_spread) + int(
            (i / count) * days_spread * 0.5
        )  # Spread more towards recent
        days_ago = min(days_ago, days_spread + 30)  # Cap how far back random items go
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        seconds_ago = random.randint(0, 59)
        timestamp = now - timedelta(
            days=days_ago, hours=hours_ago, minutes=minutes_ago, seconds=seconds_ago
        )
        timestamps.append(timestamp)
    return sorted(timestamps)


# --- Seed Data (copied from your CSV generation script) ---

headphone_seed_data = [
    {
        "review": "The sound quality is absolutely phenomenal for the price. I've been using them for a month now and I'm still blown away. A truly fantastic value.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the sound quality is absolutely fantastic.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer mentions that the price is absolutely fantastic.'}]}",
    },
    {
        "review": "Incredibly comfortable for long listening sessions. The build quality feels very premium and durable. I'm very impressed with the overall package.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very impressed with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the build quality is very strong.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The packaging was a bit over the top, but it definitely protected the headphones during shipping. The sound is great, but the bass could be a little stronger for my taste.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Sound quality is great.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 2, 'justification': 'The earphones were a bit more than the other earphones.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I had a question about the warranty and the customer support team was incredibly helpful and friendly. They resolved my issue within minutes. The headphones themselves are excellent.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product and the support.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is excellent.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer had an excellent experience with the support team.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The fit is a little tight on my head, but I'm hoping they'll loosen up over time. The noise cancellation is surprisingly effective for this price range.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Generally positive experience with some minor issues.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 4, 'justification': 'Generally positive experience with some minor issues.'}]}",
    },
    {
        "review": "An amazing all-around pair of headphones. They look great, sound fantastic, and are very comfortable to wear. I couldn't be happier with my purchase.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product, calling it amazing and stating they would purchase it again.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the sound is fantastic, indicating high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The sound quality is decent, but the materials feel a bit cheap. The carrying case that came with it is a nice bonus though.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 3, 'justification': 'The reviewer finds the product decent but has some issues with the sound quality.'}, {'name': 'Quality', 'rating': 3, 'justification': 'The reviewer finds the sound quality decent but mentions that it feels cheap.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 4, 'justification': 'The reviewer finds the sound quality to be decent.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I was hesitant to buy headphones online without trying them on first, but these fit perfectly. The sound isolation is also a huge plus.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The sound quality is perfect.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'The earbuds fit perfectly.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The battery life is incredible. I can go for days without needing to charge them. The packaging was also very sleek and professional.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The battery life is very impressive.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'The packaging is very protective and the battery is very light.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I'm not an audiophile, but these sound amazing to me. A huge step up from my old earbuds. The unboxing experience was also very satisfying.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The sound quality is amazing.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The design is very stylish and modern. They're lightweight and don't feel bulky at all. The sound is well-balanced across all frequencies.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The sound is very clear and the sound system is well balanced.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The sound is very clear and the sound system is well balanced.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "Connecting to my phone was a breeze. The instructions in the manual were very clear and easy to follow. The sound quality is top-notch.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The product is very easy to use and has a great quality sound.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is very easy to use and has a great quality sound.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The included charging cable is a bit on the short side. Other than that, I'm happy with the performance for what I paid.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally satisfied with the product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 4, 'justification': 'Generally satisfied with the product.'}]}",
    },
    {
        "review": "I've been using these for a few months now and they've held up really well. The build quality is excellent and they still sound as good as the day I got them.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product, mentioning that it has held up well and has been excellent quality.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the build quality is excellent and the product has held up well.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The earcups are so soft and plush. I can wear these for hours without any discomfort. The soundstage is also surprisingly wide.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product, mentioning that it is soft, comfortable, and has a nice sound.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the ear cushions are soft and comfortable, indicating high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I had an issue with my initial order, but the support team was fantastic and sent a replacement right away. Great service and a great product.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product and the support.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product was a great replacement.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer received a replacement and the support team was helpful.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I was worried they might feel flimsy, but they have a nice weight to them and feel very sturdy. The sound is a little bass-heavy, but I like that.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive with some minor complaints.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Generally sturdy, but flimsy.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The value you get for your money is outstanding. You could easily spend twice as much on headphones that don't sound this good.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is of good quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer feels that the product is a good value for the price.'}]}",
    },
    {
        "review": "The adjustable headband is a great feature. It allows for a perfect fit, no matter your head size. The clarity of the audio is impressive.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The ear tips are flexible and comfortable.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'The ear tips are perfect for the reviewer's ears.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The packaging felt very premium and made it feel like I was opening a high-end product. The sound did not disappoint either!",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The reviewer is generally satisfied with the product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The sound quality was very good.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'The packaging was very nice.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I'm hearing new details in my favorite songs that I've never noticed before. The sound is so crisp and clear. An excellent investment.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product, calling it a 'life changing' purchase.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the sound is so clear and beautiful, indicating high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The reviewer is impressed with the sound, calling it a 'life changing' purchase, indicating a positive description.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer is satisfied with the purchase, indicating a positive value.'}]}",
    },
    {
        "review": "They feel very durable and well-constructed. I'm confident they'll last me a long time. The included carrying pouch is a nice touch.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the bag is very durable.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I wish they came in a few more color options, but the classic black and silver is very sleek. For the price, the sound quality is unbeatable.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally satisfied with the product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The sound quality is very good.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The price is very reasonable.'}]}",
    },
    {
        "review": "Shipping was incredibly fast and the headphones were securely packaged. The whole experience from purchase to listening has been excellent.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with their purchase experience.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product was of excellent quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'The product was packaged with great care.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The noise cancellation isn't the best on the market, but it's more than adequate for my daily commute. The comfort level is top-notch.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with the product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I'm really impressed with the overall quality of these headphones. They feel like they should have cost a lot more than they did.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'impressed with the quality of the headphones'}, {'name': 'Quality', 'rating': 4, 'justification': 'impressed with the quality of the headphones'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 4, 'justification': 'impressed with the quality of the headphones'}, {'name': 'Value', 'rating': 4, 'justification': 'impressed with the quality of the headphones'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not",
    },
    {
        "review": "The controls on the earcup are intuitive and easy to use. The microphone quality for calls is also surprisingly good.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The product is easy to use and has good quality.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The product is easy to use and has good quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "A fantastic product all around. From the moment I opened the box, I could tell this was a quality item. The sound lives up to the presentation.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the sound quality is 'amazing'.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "They're a little on the bulky side, but the sound quality more than makes up for it. The earcups are very spacious and don't put pressure on my ears.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The sound quality is very good.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I had a seamless experience with their customer service. They were very responsive and helpful. It's great to see a company that stands behind its products.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product and service.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product was very flexible and comfortable.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer appreciated the support from the company.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The highs and mids are crystal clear, making vocals and instruments sound amazing. The bass is present but not overpowering.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product, mentioning its high quality and clear sound.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer praises the high quality of the instrument, mentioning that the strings are clear and the sound is amazing.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The reviewer is impressed with the clear sound and high quality of the instrument, indicating a good description.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "For the price, you'd be hard-pressed to find a better combination of comfort, style, and sound quality. A definite five-star product.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer gave the product 5 stars, indicating a very positive experience.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentioned that the product is a better quality than the standard, indicating a high quality product.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer mentioned that the product is a great value, indicating a good price for the quality.'}]}",
    },
    {
        "review": "The packaging was minimal and eco-friendly, which I appreciate. The headphones themselves have a very clean and understated design.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is a nice and clean sound.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 4, 'justification': 'The reviewer mentions that the packaging was a bit thin.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product description.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The battery seems to last forever. I use them every day and only have to charge them about once a week. The sound is also consistently good.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product, mentioning it lasts a long time and is good for their needs.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions the battery lasts a long time, indicating high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer mentions the product is good for their needs, implying good value for the price.'}]}",
    },
    {
        "review": "A solid pair of headphones that punches well above its weight. The sound is rich and detailed, and they feel like they're built to last.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The sound quality is solid.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The customer support team went above and beyond to help me with a minor issue. It's refreshing to deal with such a professional and helpful company.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product and the service provided.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is described as reliable and effective.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer appreciates the helpful and responsive support from the company.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The fit is very secure, making them great for when I'm on the move. The sound isolation is also quite effective, even in noisy environments.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The product is very effective in securing the fit of the air purifier.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is very effective in securing the fit of the air purifier.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'The product is very effective in securing the fit of the air purifier.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I'm so glad I chose these headphones. They offer a premium experience without the premium price tag. Highly recommended.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'Highly recommended.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'Highly recommend.'}]}",
    },
    {
        "review": "The unboxing felt special. They've paid a lot of attention to the presentation. The sound is immersive and enjoyable.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer enjoyed the product and found it enjoyable.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The sound was enjoyable.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The sound was enjoyable.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "These headphones are a game-changer. The clarity and depth of the audio are on another level. I'm rediscovering my music collection.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product, calling it a game-changer and a must-have for music lovers.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the sound quality is exceptional, with a clear and detailed sound.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The reviewer is impressed with the product's ability to transform any music into a new sound, making it a must-have for music lovers.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product, calling it a game-changer and a must-have for music lovers.'}]}",
    },
    {
        "review": "මේ මිලට සින්දු අහන්න නියමයි. සද්දෙත් නියමයි. ඇත්තටම වටිනවා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer thinks the product is a great deal.'}]}",
    },
    {
        "review": "ගොඩක් වෙලා දාගෙන ඉන්න පුළුවන්, කිසිම අපහසුවක් නෑ. හදලා තියෙන විදිහත් ගොඩක් හොඳයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is easy to use and has a long lifespan.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "පැකේජ් එක නම් ටිකක් ලොකුයි වගේ, ඒත් බඩුවට මුකුත් වෙලා තිබ්බෙ නෑ. සද්දෙ හොඳයි, ඒත් බේස් තව ටිකක් තිබ්බනම් හොඳයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with the product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "වගකීම ගැන ප්‍රශ්නයක් අහන්න කතා කලාම එයාලගෙ සේවාව නම් නියමයි. මගේ ප්‍රශ්නෙ ඉක්මනට විසඳුවා. හෙඩ්ෆෝන් එකත් සුපිරි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is'superior'.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer mentions that the product is'superior' and the support team is 'quick'.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "මගේ ඔළුවට ටිකක් හිරයි වගේ, ඒත් පාවිච්චි කරද්දි හරියයි හිතනවා. මේ ගානට සද්දෙ ඇහෙන්නෙ නැති වෙන එක නම් හොඳටම වටිනවා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive review with some minor complaints.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "හැම අතින්ම නියම හෙඩ්ෆෝන් එකක්. ලස්සනයි, සද්දෙත් නියමයි, දාගෙන ඉන්නත් සනීපයි. ගත්තට ගොඩක් සතුටුයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is great.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "සද්දෙ හොඳයි, ඒත් හදලා තියෙන බඩු ටිකක් චීප් වගේ. ඒත් එක්ක ආපු පවුච් එක නම් හොඳයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive review with some minor complaints.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Generally positive review with some minor complaints.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ඔන්ලයින් බලලා ට්‍රයි කරන්නෙ නැතුව ගන්න බය හිතුනා, ඒත් මේක මට ගානටම හරි. සද්දෙ එළියට ඇහෙන්නෙ නැති එකත් නියමයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "බලන්න ලස්සනයි, අතට ගත්තමත් හොඳ බරක් තියෙනවා. ශක්තිමත් වගේ. සද්දෙ බේස් ටිකක් වැඩියි, ඒත් මම ඒකට කැමතියි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive review with some minor complaints.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The reviewer mentions that the product is well-made and has a nice sound.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ගෙවන ගානට නම් උපරිම වටිනවා. මේ වගේ හොඳ සද්දයක් තියෙන හෙඩ්ෆෝන් මේ ගානට හොයාගන්න අමාරුයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer thinks the product is a good value.'}]}",
    },
    {
        "review": "ඔළුවෙ සයිස් එකට හදාගන්න පුළුවන් එක ලොකු දෙයක්. ඒක නිසා ඕනම කෙනෙක්ට දාන්න පුළුවන්. සද්දෙ පැහැදිලිව ඇහෙනවා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "පැකේජ් එක දැක්කම හිතුනා ගොඩක් වටින බඩුවක් කියලා. සද්දෙත් ඒ වගේමයි!",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "මම කවදාවත් අහලා නැති විස්තර මගේ සින්දුවලින් දැන් ඇහෙනවා. සද්දෙ හරිම පැහැදිලියි. නියම ආයෝජනයක්.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product, calling it a 'great deal' and stating they will 'love it'.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product description, stating it is 'just the right amount'.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product, calling it a 'great deal'.'}]}",
    },
    {
        "review": "ගොඩක් කල් පාවිච්චි කරන්න පුළුවන් වගේ. හදලා තියෙන විදිහ හොඳයි. ඒත් එක්ක දෙන පවුච් එකත් හොඳයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is good quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "වෙන පාටවල් තිබ්බනම් හොඳයි, ඒත් මේ කළුයි රිදියි පාටත් ලස්සනයි. මේ මිලට සද්දෙ නම් සුපිරි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the color is perfect.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ඉක්මනටම ගෙදරට ආවා, හොඳට පැක් කරලා තිබ්බා. ගත්ත වෙලේ ඉඳන් සින්දු අහනකම්ම හැමදේම නියමයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is great.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "වටේ සද්දෙ ඇහෙන්නෙ නැති වෙන එක ලොකුවටම නෑ, ඒත් දවස ගානෙ පාවිච්චියට ඇති. දාගෙන ඉන්න නම් හරිම සනීපයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is durable and has a long lifespan.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "මේ හෙඩ්ෆෝන් එකේ කොලිටිය ගැන මම පුදුම වුනා. මේවට මීට වඩා ගොඩක් වියදම් වෙන්න ඕන වගේ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is not satisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is not as good as expected.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "කනේ තියෙන බට්න් පාවිච්චි කරන්න ලේසියි. කෝල් ගන්නකොට මයික් එකේ සද්දෙත් හොඳට ඇහෙනවා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The product seems to be working as expected.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product seems to be working as expected.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "සම්පූර්ණයෙන්ම නියම බඩුවක්. පෙට්ටිය ඇරපු වෙලේම හිතුනා මේක හොඳ බඩුවක් කියලා. සද්දෙත් ඒ වගේමයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is excellent.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ටිකක් ලොකුයි වගේ, ඒත් සද්දෙට ඒක අමතක වෙනවා. කන් දෙක හොඳට වැහෙන නිසා කනට පීඩනයක් නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive review with some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Generally positive review with some minor issues.'}, {'name': 'Sizing', 'rating': 4, 'justification': 'Generally positive review with some minor issues.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "එයාලගෙ පාරිභෝගික සේවාව නම් නියමයි. ඉක්මනට උත්තර දුන්නා, උදව් කලා. තමන්ගෙ බඩු ගැන වගකීමක් තියෙන සමාගමක් දැක්කම සතුටුයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product and the company.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer appreciates the company's support.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "උස් සහ මධ්‍යම සද්ද හරිම පැහැදිලියි, ඒ නිසා කටහඬවල් සහ සංගීත භාණ්ඩ හරි ලස්සනට ඇහෙනවා. බේස් එකත් තියෙනවා, ඒත් ඕනවට වඩා නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the sound quality is great.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "මේ මිලට, මේ වගේ සනීපයක්, ලස්සනක් සහ සද්දයක් තියෙන එකක් හොයාගන්න අමාරුයි. අනිවාර්යයෙන්ම තරු පහේ බඩුවක්.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is of high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer thinks the product is a good value.'}]}",
    },
    {
        "review": "පැකේජ් එක පොඩියි, පරිසරයටත් හොඳයි, ඒක මම අගය කරනවා. හෙඩ්ෆෝන් එකේ පෙනුමත් හරිම සරලයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "බැටරිය නම් ඉවරයක් වෙන්නෙම නෑ වගේ. මම හැමදාම පාවිච්චි කරනවා, සතියකට සැරයක් වගේ චාජ් කරන්නෙ. සද්දෙත් හැමතිස්සෙම හොඳයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the battery lasts a long time, indicating high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "මේක නියම හෙඩ්ෆෝන් එකක්. සද්දෙ ගොඩක් විස්තරාත්මකයි, හදලා තියෙන්නෙත් කල් පවතින විදිහට.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is'superb'.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product description.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "පාරිභෝගික සේවා කණ්ඩායම මගේ පොඩි ප්‍රශ්නෙකට උදව් කරන්න ගොඩක් මහන්සි වුනා. ඒ වගේ වෘත්තීය සහ උදව්කාර සමාගමක් එක්ක ගනුදෙනු කරන්න ලැබීම සතුටක්.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product, mentioning it helped them with their business.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer mentions that the product helped them with their business, implying good support.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "හොඳට හිරවෙලා තියෙන නිසා එහා මෙහා යද්දිත් ලේසියි. සෙනග ඉන්න තැන්වලදිත් පිට සද්දෙ ඇහෙන්නෙ නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The product is well-made and easy to use.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is well-made.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "මම මේ හෙඩ්ෆෝන් එක තෝරගත්ත එක ගැන සතුටු වෙනවා. ලොකු ගානක් නැතුව වටින අත්දැකීමක් දෙනවා. අනිවාර්යයෙන්ම නිර්දේශ කරනවා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product, mentioning it is a game-changer and they would recommend it to others.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer feels the product is a game-changer and would recommend it, indicating a good value for the price.'}]}",
    },
    {
        "review": "இந்த விலைக்கு ஒலித் தரம் மிகவும் அருமை. நான் ஒரு மாதமாகப் பயன்படுத்துகிறேன், இன்னும் ஆச்சரியமாக இருக்கிறது. உண்மையிலேயே ஒரு சிறந்த மதிப்பு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is very durable.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer mentions that the product is a great value.'}]}",
    },
    {
        "review": "நீண்ட நேரம் கேட்க மிகவும் வசதியாக இருக்கிறது. உருவாக்கத் தரம் மிகவும் பிரீமியம் மற்றும் நீடித்ததாக உணர்கிறது. ஒட்டுமொத்த தொகுப்பிலும் நான் மிகவும் ஈர்க்கப்பட்டேன்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product, mentioning it is the best they've ever used.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is of high quality, with a durable and comfortable design.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "பேக்கேஜிங் கொஞ்சம் அதிகமாக இருந்தது, ஆனால் அது நிச்சயமாக ஹெட்ஃபோன்களைப் பாதுகாத்தது. ஒலி நன்றாக இருக்கிறது, ஆனால் பாஸ் என் சுவைக்கு இன்னும் கொஞ்சம் வலுவாக இருந்திருக்கலாம்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The earbuds are decent quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "உத்தரவாதத்தைப் பற்றி ஒரு கேள்வி இருந்தது, வாடிக்கையாளர் ஆதரவுக் குழு நம்பமுடியாத அளவிற்கு உதவியாகவும் நட்பாகவும் இருந்தது. அவர்கள் என் பிரச்சினையை சில நிமிடங்களில் தீர்த்தார்கள். ஹெட்ஃபோன்கள் தாங்களாகவே சிறந்தவை.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product, stating it was a game-changer and the customer service was excellent.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is a game-changer, implying high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer praises the customer service, stating it was excellent.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "என் தலைக்கு கொஞ்சம் இறுக்கமாக இருக்கிறது, ஆனால் காலப்போக்கில் அவை ढीலமாகிவிடும் என்று நம்புகிறேன். இந்த விலை வரம்பில் இரைச்சல் ரத்துசெய்தல் வியக்கத்தக்க வகையில் பயனுள்ளதாக இருக்கிறது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The reviewer is generally satisfied with the product, mentioning it is a great tool for relieving tension.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The reviewer mentions the product is a great tool, indicating good quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ஒரு அற்புதமான ஆல்-ரவுண்ட் ஹெட்ஃபோன்கள். அவை அழகாக இருக்கின்றன, அருமையாக ஒலிக்கின்றன, மேலும் அணிய மிகவும் வசதியாக இருக்கின்றன. என் வாங்குதலில் நான் மகிழ்ச்சியாக இருக்க முடியாது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product, calling it 'the best' and 'fantastic'.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is 'the best' and 'fantastic', indicating high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ஒலித் தரம் கண்ணியமானது, ஆனால் பொருட்கள் கொஞ்சம் மலிவானதாக உணர்கின்றன. அதனுடன் வந்த கேரிங் கேஸ் ஒரு நல்ல போனஸ்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The reviewer finds the product to be a good value for the price.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The reviewer mentions that the product is well made.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 4, 'justification': 'The reviewer finds the product to be a good value for the price.'}]}",
    },
    {
        "review": "முதலில் அவற்றை முயற்சிக்காமல் ஆன்லைனில் ஹெட்ஃபோன்கள் வாங்கத் தயங்கினேன், ஆனால் இவை எனக்குப் பொருத்தமாகப் பொருந்துகின்றன. ஒலி தனிமைப்படுத்தலும் ஒரு பெரிய பிளஸ்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "பேட்டரி ஆயுள் நம்பமுடியாதது. சார்ஜ் செய்யத் தேவையில்லாமல் நான் பல நாட்கள் செல்ல முடியும். பேக்கேஜிங்கும் மிகவும் நேர்த்தியாகவும் தொழில் ரீதியாகவும் இருந்தது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The battery life is excellent.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "நான் ஒரு ஆடியோஃபைல் அல்ல, ஆனால் இவை எனக்கு அருமையாக ஒலிக்கின்றன. என் பழைய இயர்பட்ஸிலிருந்து ஒரு பெரிய படி மேலே. அன்பாக்சிங் அனுபவமும் மிகவும் திருப்திகரமாக இருந்தது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product, mentioning it was excellent and they are excited to continue using it.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is excellent, indicating high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "வடிவமைப்பு மிகவும் ஸ்டைலாகவும் நவீனமாகவும் இருக்கிறது. அவை இலகுவானவை மற்றும் பருமனாக உணரவில்லை. ஒலி அனைத்து அதிர்வெண்களிலும் நன்கு சமநிலையில் உள்ளது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The product is highly rated and has a strong, clear sound quality.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product has a strong, clear sound quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The product description is clear and accurate.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "என் தொலைபேசியுடன் இணைப்பது ஒரு தென்றலாக இருந்தது. கையேட்டில் உள்ள வழிமுறைகள் மிகவும் தெளிவாகவும் பின்பற்ற எளிதாகவும் இருந்தன. ஒலித் தரம் முதல் வகுப்பு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer found the product to be very helpful and effective.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is described as very effective.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The product is described as very helpful and effective.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "சேர்க்கப்பட்ட சார்ஜிங் கேபிள் கொஞ்சம் குறுகிய பக்கத்தில் உள்ளது. அதைத் தவிர, நான் செலுத்தியதற்கு செயல்திறனில் நான் மகிழ்ச்சியாக இருக்கிறேன்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The reviewer is generally satisfied with the product, mentioning it is a great option for a small space.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "நான் இப்போது சில மாதங்களாக இவற்றைப் பயன்படுத்துகிறேன், அவை நன்றாகவே உள்ளன. உருவாக்கத் தரம் சிறந்தது, அவை நான் வாங்கிய நாள் போலவே நன்றாக ஒலிக்கின்றன.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is of high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "இயர்கப்கள் மிகவும் மென்மையாகவும் மென்மையாகவும் இருக்கின்றன. எந்த அசௌகரியமும் இல்லாமல் நான் இவற்றை மணிநேரம் அணியலாம். சவுண்ட்ஸ்டேஜும் வியக்கத்தக்க வகையில் அகலமானது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is described as'super soft' and'super strong', indicating high quality.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'The product is described as'super soft', indicating a comfortable fit.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The product is described as'super soft' and'super strong', indicating accurate description.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "என் ஆரம்ப ஆர்டரில் எனக்கு ஒரு சிக்கல் இருந்தது, ஆனால் ஆதரவுக் குழு அருமையாக இருந்தது, உடனடியாக மாற்றீட்டை அனுப்பியது. சிறந்த சேவை மற்றும் ஒரு சிறந்த தயாரிப்பு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer had a great experience with the product, mentioning it was excellent and the customer service was excellent.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product was described as excellent.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The customer service was excellent.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "அவை மெல்லியதாக உணரக்கூடும் என்று நான் கவலைப்பட்டேன், ஆனால் அவை ஒரு நல்ல எடையைக் கொண்டுள்ளன, மேலும் மிகவும் உறுதியானதாக உணர்கின்றன. ஒலி கொஞ்சம் பாஸ்-ஹெவி, ஆனால் எனக்கு அது பிடிக்கும்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with the product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The product is described as firm and comfortable.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 4, 'justification': 'The product is described as firm and comfortable.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "உங்கள் பணத்திற்கான மதிப்பு அட்டவணையில் இல்லை. இந்த விலை புள்ளியில் இவ்வளவு நன்றாக ஒலிக்காத ஹெட்ஃபோன்களை நீங்கள் காண முடியாது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer mentions that the price is very good.'}]}",
    },
    {
        "review": "சரிசெய்யக்கூடிய ஹெட் பேண்ட் ஒரு சிறந்த அம்சமாகும். இது உங்கள் தலை அளவைப் பொருட்படுத்தாமல் சரியான பொருத்தத்தை அனுமதிக்கிறது. ஆடியோவின் தெளிவு ஈர்க்கக்கூடியது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The product is well designed and functional.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is well designed and functional.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The product is well designed and functional.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "பேக்கேஜிங் மிகவும் பிரீமியமாக உணர்ந்தது, மேலும் நான் ஒரு உயர்நிலை தயாரிப்பைத் திறப்பது போல் உணர்ந்தேன். ஒலியும் ஏமாற்றமடையவில்லை!",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is described as having a high-quality sound.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'The product was packaged with care and arrived in excellent condition.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "நான் முன்பு ஒருபோதும் கவனிக்காத என் விருப்பமான பாடல்களில் புதிய விவரங்களைக் கேட்கிறேன். ஒலி மிகவும் தெளிவாகவும் தெளிவாகவும் இருக்கிறது. ஒரு சிறந்த முதலீடு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer highly recommends the product, calling it a'must have'.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the music is 'beautifully clear'.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The reviewer mentions that the product is 'beautifully clear'.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "அவை மிகவும் நீடித்ததாகவும் நன்கு கட்டப்பட்டதாகவும் உணர்கின்றன. அவை நீண்ட காலம் நீடிக்கும் என்று நான் நம்புகிறேன். சேர்க்கப்பட்ட கேரிங் பவுச் ஒரு நல்ல தொடுதல்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is described as durable and has a long-lasting quality.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The product is described as having a unique design and being able to be used as a storage container.'}, {'name': 'Value', 'rating': 5, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "நான் இன்னும் சில வண்ண விருப்பங்களில் வர விரும்புகிறேன், ஆனால் கிளாசிக் கருப்பு மற்றும் வெள்ளி மிகவும் நேர்த்தியாக இருக்கிறது. விலைக்கு, ஒலித் தரம் வெல்ல முடியாதது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive review with some minor complaints.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "கப்பல் போக்குவரத்து நம்பமுடியாத அளவிற்கு வேகமானது மற்றும் ஹெட்ஃபோன்கள் பாதுகாப்பாக தொகுக்கப்பட்டன. வாங்குவதிலிருந்து கேட்பது வரையிலான முழு அனுபவமும் சிறப்பாக உள்ளது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is extremely satisfied with the product, mentioning it is a great deal and the customer service is excellent.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions the product is a great deal and the customer service is excellent, indicating high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer mentions the customer service is excellent, indicating high support.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 5, 'justification': 'The reviewer mentions the product is a great deal, indicating high value.'}]}",
    },
    {
        "review": "இரைச்சல் ரத்துசெய்தல் சந்தையில் சிறந்ததல்ல, ஆனால் என் தினசரி பயணத்திற்கு இது போதுமானது. ஆறுதல் நிலை முதல் வகுப்பு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally satisfactory product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Generally satisfactory product.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "இந்த ஹெட்ஃபோன்களின் ஒட்டுமொத்த தரத்தில் நான் மிகவும் ஈர்க்கப்பட்டேன். அவை செய்ததை விட மிக அதிகமாக செலவாகும் என்று அவை உணர்கின்றன.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The reviewer is generally satisfied with the product, but mentions that it's not the best option.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The reviewer mentions that the product is extremely light, implying a high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 4, 'justification': 'The reviewer mentions that the product is a great value for the price.'}]}",
    },
    {
        "review": "இயர்கப்பில் உள்ள கட்டுப்பாடுகள் உள்ளுணர்வு மற்றும் பயன்படுத்த எளிதானவை. அழைப்புகளுக்கான மைக்ரோஃபோன் தரமும் வியக்கத்தக்க வகையில் நன்றாக இருக்கிறது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "சுற்றிலும் ஒரு அருமையான தயாரிப்பு. நான் பெட்டியைத் திறந்த தருணத்திலிருந்து, இது ஒரு தரமான பொருள் என்று சொல்ல முடிந்தது. ஒலி விளக்கக்காட்சிக்கு ஏற்ப வாழ்கிறது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is described as 'the best'.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 5, 'justification': 'The product is described as 'the best'.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "அவை பருமனான பக்கத்தில் கொஞ்சம் உள்ளன, ஆனால் ஒலித் தரம் அதை ஈடுசெய்வதை விட அதிகம். இயர்கப்கள் மிகவும் விசாலமானவை, என் காதுகளில் அழுத்தம் கொடுக்க வேண்டாம்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive review with some minor complaints.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The product is described as 'firm', indicating good quality.'}, {'name': 'Sizing', 'rating': 4, 'justification': 'The product is described as'slightly firm', indicating a suitable size.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "அவர்களின் வாடிக்கையாளர் சேவையுடன் எனக்கு ஒரு தடையற்ற அனுபவம் இருந்தது. அவர்கள் மிகவும் பதிலளிக்கக்கூடியவர்களாகவும் உதவிகரமாகவும் இருந்தார்கள். ஒரு நிறுவனம் அதன் தயாரிப்புகளுக்குப் பின்னால் நிற்பதைப் பார்ப்பது மிகவும் நல்லது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product and the support.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product is of high quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 5, 'justification': 'The reviewer appreciates the support from the company.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
]

charger_seed_data = [
    {
        "review": "This charger stopped working after just one month. The build quality is really poor and feels very flimsy. Not worth the money at all.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it stopped working after a month and is not worth the money.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product stopped working after a month, indicating poor quality.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer states that the product is not worth the money.'}]}",
    },
    {
        "review": "It charges my phone incredibly slowly. My old charger was much faster. A complete waste of money and time. Very disappointed with the overall performance.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'Very disappointed with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The charger is extremely slow and the battery life is very short.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The product is a waste of money.'}]}",
    },
    {
        "review": "The packaging was fine, but the charger itself gets dangerously hot when plugged in. I'm afraid to leave it unattended. A major safety concern.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is generally dissatisfied with the product due to a safety issue.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer is generally dissatisfied with the product due to a safety issue.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 1, 'justification': 'The packaging is hazardous due to a safety issue.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I tried contacting their support team about the slow charging issue and never got a response. Terrible customer service. The product is just as bad.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'Terrible experience with terrible customer service.'}, {'name': 'Quality', 'rating': 1, 'justification': 'Terrible customer service.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'Terrible customer service.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "It works, but the cable is way too short. For the price, I was expecting something much more substantial. It's just an average, overpriced product.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The product works, but it's overpriced.'}, {'name': 'Quality', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The price is too high.'}]}",
    },
    {
        "review": "This is not a fast charger as advertised. It takes hours to get a decent charge. I feel completely misled. The value is just not there.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the charger is not as good as advertised.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 1, 'justification': 'The reviewer feels that the product does not match the description.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer feels that the product is not worth the price.'}]}",
    },
    {
        "review": "The prongs that go into the socket bent after a few uses. The materials used are clearly very cheap. I wouldn't recommend this to anyone.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is very cheap and would not recommend it.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is very cheap, implying poor quality.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer states that the product is very cheap, implying poor value.'}]}",
    },
    {
        "review": "The box it came in was nice and compact. The charger itself is also small, but it makes a weird buzzing sound while charging. It's a bit unsettling.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 3, 'justification': 'The product has some good qualities but also some issues.'}, {'name': 'Quality', 'rating': 3, 'justification': 'The product has some good qualities but also some issues.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 1, 'justification': 'The packaging is a bit small and the box is a bit flimsy.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "DO NOT BUY. This charger completely fried my phone's battery. I had to get a new phone. I tried contacting support and they were useless.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer strongly advises against purchasing the product due to its poor performance and lack of support.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product completely failed to charge the reviewer's phone, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer had a terrible experience with the product, indicating poor support.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The shipping was fast and the packaging was secure. The charger works as expected, though it doesn't feel as premium as the one that came with my phone.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The product works as expected and is fast.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The product works as expected.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'The charging cable is fast.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "It's a very tight fit in the wall socket, and I'm worried it will break my outlet. The overall design feels poorly thought out.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is generally dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product feels poor in the tight space, indicating a low quality.'}, {'name': 'Sizing', 'rating': 1, 'justification': 'The reviewer mentions that the product feels poor in the tight space, indicating a poor fit.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "Stopped working completely after a week. I threw it in the trash. Don't waste your money on this garbage. Poor quality.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'Poor quality and stopped working after a few months.'}, {'name': 'Quality', 'rating': 1, 'justification': 'Poor quality and stopped working after a few months.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'rating': 1, 'justification': 'Poor quality and stopped working after a few months, indicating poor value for money.'}]}",
    },
    {
        "review": "For the price, I guess it's okay. But it definitely doesn't live up to the claims of 'fast charging'. It's mediocre at best.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer finds the product to be mediocre.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer finds the product to be mediocre.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 1, 'justification': 'The reviewer finds the product to be low on power.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer finds the product to be overpriced.'}]}",
    },
    {
        "review": "The indicator light is way too bright. I have to cover it at night. It's a small annoyance, but it speaks to a lack of attention to detail in the design.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The product has some positive and negative aspects, but overall it is a disappointment.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The product has some positive and negative aspects, but overall it is a disappointment.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 1, 'justification': 'The product does not have a clear and simple design.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I had an issue with the product and the support team was unhelpful and rude. I regret this purchase immensely.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer was extremely dissatisfied with their purchase experience.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product was described as having a problem with the user, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer was extremely dissatisfied with the support they received.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I must have gotten a good one because mine works perfectly. It charges my phone quickly and doesn't overheat. The packaging was simple and effective.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product works perfectly.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'The packaging is simple and effective.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The quality is just not there. The plastic feels brittle and I'm sure it will crack if I drop it. Not a durable product.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is not satisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the plastic feels like it is not durable.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'justification': 'Not mentioned in the review.', 'rating': 0}]}",
    },
    {
        "review": "This charger is a joke. It takes longer to charge my phone than using my laptop's USB port. A terrible value proposition.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer thinks the product is a waste of money.'}]}",
    },
    {
        "review": "The packaging is sleek, but the performance is lacking. It does the job, but very slowly. I wouldn't buy it again.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is not satisfied with the product due to its performance.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer mentions that the product does not perform as expected.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 4, 'justification': 'The reviewer mentions that the packaging is very light.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I'm very concerned about how hot this gets. It doesn't seem safe. The build quality feels cheap and lightweight.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is generally dissatisfied with the product.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer mentions that the product feels cheap.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "My phone actually loses charge when plugged into this thing while I'm using it. It's completely useless. Bad quality.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is of poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "It's a decent backup charger. The size is convenient for travel. The packaging was minimal, which I appreciate.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with the product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'The product is a decent size.'}, {'name': 'Packaging', 'rating': 4, 'justification': 'The packaging was adequate.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The cable started fraying at the connection point after only a couple of weeks. Poor durability and definitely not worth the price.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'Poor product, poor durability, poor support.'}, {'name': 'Quality', 'rating': 1, 'justification': 'Poor durability, poor support.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'Poor support.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'Not worth the price.'}]}",
    },
    {
        "review": "Their customer support is a black hole. Emails go unanswered. Don't expect any help if you have a problem. The product itself is low quality.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product and the company.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions low quality and low quality is low.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer mentions low quality and low quality is low, implying poor support.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "It looks nice in the pictures, but in person, it just feels cheap. The charging speed is also very underwhelming. Not a good value.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'Not a good product.'}, {'name': 'Quality', 'rating': 2, 'justification': 'Not cheap.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 1, 'justification': 'Not cheap.'}, {'name': 'Value', 'rating': 1, 'justification': 'Not cheap.'}]}",
    },
    {
        "review": "This charger damaged the charging port on my phone. An expensive repair because of a cheap, low-quality product. Avoid at all costs.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer strongly dislikes the product due to its poor quality and low price.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is of low quality and damaged.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer mentions that the product is cheap, but the low quality makes it a poor value.'}]}",
    },
    {
        "review": "The box looked professional, but the product inside didn't match. It's a very basic, slow charger. You can find better for the same price.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is generally dissatisfied with the product.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The product looks and feels like a cheap one.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 1, 'justification': 'The product was not as described, with the charger being a different color.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The product is not worth the price.'}]}",
    },
    {
        "review": "Overheats constantly. I have to unplug it to let it cool down. This can't be good for the charger or my phone in the long run. Poor quality.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'Poor quality and poor performance.'}, {'name': 'Quality', 'rating': 1, 'justification': 'Poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I bought two of these and both of them failed within a month. Clearly a manufacturing quality issue. Terrible value for money.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'Terrible purchase, terrible quality, and terrible value.'}, {'name': 'Quality', 'rating': 1, 'justification': 'Terrible quality, a single unit failed within 6 months.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'rating': 1, 'justification': 'Terrible value, a single unit failed within 6 months.'}]}",
    },
    {
        "review": "The compact size is the only good thing about it. It fits well in my bag. However, the slow charging is a major drawback.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with some drawbacks.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Generally positive experience with some drawbacks.'}, {'name': 'Sizing', 'rating': 2, 'justification': 'The size is smaller than expected.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "I expected better quality for this price. The plastic casing creaks when I plug it in. It doesn't inspire confidence.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is generally dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is of poor quality.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'justification': 'Not mentioned in the review.', 'rating': 0}]}",
    },
    {
        "review": "Their support team promised a replacement that never arrived. Don't trust their promises. The product is not reliable either.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product and the company's support.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product is not reliable and the company's support is unresponsive.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The company's support is unresponsive.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The packaging was unnecessarily large for such a small item. The charger itself is a disappointment, very slow.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is very disappointed with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the charger is very large and the battery is very small.'}, {'name': 'Sizing', 'rating': 1, 'justification': 'The reviewer mentions that the charger is very large.'}, {'name': 'Packaging', 'rating': 1, 'justification': 'The reviewer mentions that the packaging is very large.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "It worked for one day. One single day. Then it died. Absolute rubbish quality.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product stopped working after one use, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "No issues on my end. It charges my phone just fine and the size is convenient. The box was nice too.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is generally satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'The reviewer mentions that the phone fits fine.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'The reviewer mentions that the phone comes with a nice case.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "The value just isn't there. You're paying a premium for a very basic, slow, and cheaply made product.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer calls the product a 'cheap and slow' and a 'low quality'.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer thinks the product is not worth the price.'}]}",
    },
    {
        "review": "It gets so hot I can smell burning plastic. A definite fire hazard. The quality is appalling.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the quality is appalling.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "Contacted support, they were friendly but ultimately couldn't solve the slow charging issue. So, a useless product with polite but ineffective support.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer found the product to be a waste of money and had a poor experience with the charger.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer found the product to be a waste of money.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer had a poor experience with the charger.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer found the product to be a waste of money.'}]}",
    },
    {
        "review": "The packaging looked promising, making me think it was a quality item. Unfortunately, the performance is very poor. It charges at a snail's pace.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is generally dissatisfied with the product.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer mentions that the power cord is very poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 1, 'justification': 'The reviewer mentions that the power cord is very poor quality.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "This is the worst charger I have ever owned. It's slow, feels cheap, and overheats. Overall, a complete failure of a product.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The product is a total waste of money.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product is a total waste of money.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The product is a total waste of money.'}]}",
    },
    {
        "review": "මාසයක් යන්න කලින් මේ චාජරේ වැඩ නැතුව ගියා. හදලා තියෙන විදිහ හරිම දුර්වලයි. සල්ලි වලට කොහෙත්ම වටින්නේ නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is terrible and the only thing that keeps it from being a complete waste of money.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is 'terrible' and the only thing that keeps it from being a complete waste of money.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer states that the product is a 'complete waste of money'.'}]}",
    },
    {
        "review": "ෆෝන් එක චාජ් වෙන්න ගොඩක් වෙලා යනවා. මගේ පරණ චාජරේ මීට වඩා වේගවත්. සල්ලිත් කාලෙත් අපරාදේ. කොලිටිය නම් සවුත්තුයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is 'as weak as a paper clip'.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer implies that the product is overpriced.'}]}",
    },
    {
        "review": "පැකේජ් එක හොඳයි, ඒත් චාජරේ ප්ලග් කරාම භයානක විදිහට රත් වෙනවා. ගලවලා තියන්න බයයි. ආරක්ෂාව ගැන ලොකු ප්‍රශ්නයක්.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive review with some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "චාජ් වෙන්නෙ හිමින් කියලා එයාලගෙ සපෝට් එකට කතා කරන්න හැදුවා, උත්තරයක් ලැබුනෙ නෑ. හරිම නරක පාරිභෝගික සේවාවක්.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is terrible and they are not sure if they want to continue using it.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is terrible, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer is unhappy with the support, stating they are not sure if they want to continue using the product.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "වැඩ කරනවා, ඒත් කේබල් එක හරිම කොටයි. මේ ගානට මීට වඩා හොඳ දෙයක් බලාපොරොත්තු වුනා. මේක සාමාන්‍ය, ගාන වැඩි බඩුවක්.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 3, 'justification': 'The reviewer is somewhat satisfied with the product, but has some reservations.'}, {'name': 'Quality', 'rating': 3, 'justification': 'The reviewer mentions that the product is okay, but has some issues.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "දැන්වීමේ තිබ්බට මේක වේගවත් චාජරයක් නෙමෙයි. හොඳ චාජ් එකක් එන්න පැය ගානක් යනවා. මාව සම්පූර්ණයෙන්ම රැවැට්ටුවා වගේ. සල්ලි වලට වටින්නේම නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it's a waste of money and the seller is not responsive.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions the product is a waste of money, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer states the seller is not responsive.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer implies the product is overpriced.'}]}",
    },
    {
        "review": "ආපු පෙට්ටිය ලස්සනයි, පොඩියි. චාජරෙත් පොඩියි, ඒත් චාජ් වෙද්දි අමුතු සද්දයක් එනවා. ටිකක් බය හිතෙනවා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The reviewer is generally satisfied with the product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The reviewer mentions that the product is easy to use and has a simple design.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ගන්න එපා. මේ චාජරේ මගේ ෆෝන් එකේ බැටරියම නැති කලා. මට අලුත් ෆෝන් එකක් ගන්න වුනා. සපෝට් එකට කතා කලා, වැඩක් වුනේ නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product due to a faulty charger.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product is faulty, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer is unhappy with the support, as they are unable to get a replacement charger.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ඉක්මනට ආවා, හොඳට පැක් කරලා තිබ්බා. චාජරේ බලාපොරොත්තු වුන විදිහට වැඩ, ඒත් ෆෝන් එකත් එක්ක ආපු එක තරම් කොලිටියක් නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with the product.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "වෝල් සොකට් එකට හරිම හිරයි, මගේ අවුට්ලට් එක කැඩෙයි කියලා බයයි. හදලා තියෙන විදිහ හරිම දුර්වලයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is 'hairy' and 'has a lot of holes', indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "සතියකින් සම්පූර්ණයෙන්ම වැඩ නැතුව ගියා. කුණු බක්කියට දැම්මා. මේ වගේ කුණු බඩුවකට සල්ලි නාස්ති කරන්න එපා. හරිම නරක කොලිටියක්.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, calling it a 'dud' and stating it's the 'worst product I've ever had the misfortune of owning.''}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is 'dud', indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer implies that the product is not worth the cost, calling it a 'dud'.'}]}",
    },
    {
        "review": "ගානට නම් කමක් නෑ වගේ. ඒත් 'වේගවත් චාජින්' කියන කතාවට නම් කොහෙත්ම හරියන්නෙ නෑ. යන්තම් වැඩ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 3, 'justification': 'The reviewer is somewhat satisfied with the product, mentioning it works well but has some drawbacks.'}, {'name': 'Quality', 'rating': 3, 'justification': 'The reviewer mentions that the product works well, implying a decent quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ඉන්ඩිකේටර් ලයිට් එකේ එළිය හරිම සැරයි. රෑට වහන්න වෙනවා. පොඩි දෙයක් වුනාට, හදනකොට සැලකිල්ලක් නෑ කියලා තේරෙනවා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is somewhat satisfied with the product but has some concerns about the quality of the light.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer is somewhat satisfied with the product but has some concerns about the quality of the light.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "බඩුවෙ ප්‍රශ්නයක් වෙලා කතා කලාම සපෝට් ටීම් එක උදව් කලේවත් නෑ, කතා කලෙත් රළු විදිහට. මේක ගත්ත එක ගැන ගොඩක් දුක් වෙනවා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, mentioning that it was a waste of money and they're not sure if it's worth it.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product was a waste of money, implying poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer implies that the product is not worth the money, indicating poor value.'}]}",
    },
    {
        "review": "මට නම් හොඳ එකක් හම්බෙලා වගේ, මොකද මගේ එක කිසි අවුලක් නැතුව වැඩ. ෆෝන් එක ඉක්මනට චාජ් වෙනවා, රත් වෙන්නෙත් නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product works well and the batteries last a long time.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "කොලිටිය මදි. ප්ලාස්ටික් එක බිඳෙනසුලුයි, බිම වැටුනොත් කැඩෙනවා ෂුවර්. කල් පවතින බඩුවක් නෙමෙයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product is described as having a short lifespan, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "මේ චාජරේ විහිළුවක්. මගේ ලැප්ටොප් එකේ USB පෝට් එකෙන් චාජ් කරනවට වඩා වෙලා යනවා. සල්ලි වලට කිසිම වටිනාකමක් නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is a total waste of money.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer states that the product is a total waste of money.'}]}",
    },
    {
        "review": "පැකේජින් එක ලස්සනයි, ඒත් වැඩ කරන විදිහ හරි නෑ. වැඩේ වෙනවා, ඒත් හරිම හිමින්. ආයෙ නම් ගන්නෙ නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is generally dissatisfied with the product due to its low quality and lack of functionality.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is low quality and has a lot of bugs.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "මේක රත් වෙන එක ගැන මට ලොකු බයක් තියෙනවා. ඒක ආරක්ෂිත නෑ වගේ. හදලා තියෙන විදිහත් චීප්, බරක් නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is somewhat satisfied with the product but has some concerns.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer mentions that the product is not durable, but they are still using it.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ෆෝන් එක පාවිච්චි කර කර මේකට ගැහුවම චාජ් බහිනවා. කිසිම වැඩකට නෑ. නරක කොලිටිය.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is 'dumb' and has a 'dumb' sound, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "හොඳ අමතර චාජරයක්. ගමන් යන්න ලේසියි පොඩි නිසා. පැකේජ් එකත් පොඩියි, ඒක හොඳයි.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The reviewer finds the product to be useful and has a good experience with it.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'The reviewer mentions that the product is small, indicating a good fit.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "සති දෙකක් යද්දි කේබල් එක කනෙක්ෂන් එක ගාවින් නූල් ගැලවෙන්න ගත්තා. කල් පැවැත්ම අඩුයි, ගානට වටින්නෙම නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The product has a low quality and is prone to breaking.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product has a low quality and is prone to breaking.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'justification': 'Not mentioned in the review.', 'rating': 0}]}",
    },
    {
        "review": "එයාලගෙ පාරිභෝගික සේවාව වැඩක් නෑ. ඊමේල් වලට උත්තර නෑ. ප්‍රශ්නයක් වුනොත් උදව් බලාපොරොත්තු වෙන්න එපා. බඩුවත් අඩු කොලිටියක තියෙන්නෙ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product and the company.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is of poor quality and the quality is not up to the mark.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer implies that the company does not provide good support.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "පින්තූර වල ලස්සනට තිබ්බට, ඇත්තටම චීප් වගේ. චාජ් වෙන වේගෙත් හරිම මදි. හොඳ වටිනාකමක් නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is generally dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is 'low quality'.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "මේ චාජරේ මගේ ෆෝන් එකේ චාජින් පෝට් එකට හානි කලා. චීප්, අඩු කොලිටියේ බඩුවක් නිසා ලොකු වියදමක් ගියා. කොහෙත්ම ගන්න එපා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, calling it a waste of money and stating it's a poor quality product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is a poor quality product, indicating a low rating.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer implies that the product is not worth the money, indicating a low rating.'}]}",
    },
    {
        "review": "පෙට්ටිය දැක්කම හොඳ බඩුවක් කියලා හිතුනා. ඒත් ඇතුලෙ තිබ්බ එක එහෙම නෑ. හරිම සාමාන්‍ය, හිමින් චාජ් වෙන එකක්. මේ ගානට මීට වඩා හොඳ ඒවා තියෙනවා.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 3, 'justification': 'The reviewer is somewhat satisfied with the product, but has some reservations.'}, {'name': 'Quality', 'rating': 3, 'justification': 'The reviewer mentions that the product is 'just okay', indicating a neutral sentiment.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "නිතරම රත් වෙනවා. නිවෙන්න දෙන්න ගලවන්න වෙනවා. මේක දිගු කාලීනව චාජරේටවත් ෆෝන් එකටවත් හොඳ නෑ. දුර්වල කොලිටිය.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, mentioning it is a waste of money and has a low quality.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions the product is a waste of money and has a low quality, indicating poor quality.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer calls the product a waste of money, indicating poor value.'}]}",
    },
    {
        "review": "මම මේවයින් දෙකක් ගත්තා, දෙකම මාසයක් යන්න කලින් කැඩුනා. පැහැදිලිවම නිෂ්පාදන දෝෂයක්. සල්ලි වලට කිසිම වටිනාකමක් නෑ.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is broken and the seller is unresponsive.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is broken, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer states that the seller is unresponsive, indicating poor support.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer implies that the product is not worth the cost due to its poor quality and lack of support.'}]}",
    },
    {
        "review": "පොඩි සයිස් එක විතරයි හොඳ. බෑග් එකේ දාන්න ලේසියි. ඒත් හිමින් චාජ් වෙන එක ලොකු අඩුපාඩුවක්.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 3, 'justification': 'The reviewer is somewhat satisfied with the product but has some issues with its size.'}, {'name': 'Quality', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 1, 'justification': 'The reviewer finds the product to be too small.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "இந்த சார்ஜர் ஒரு மாதத்தில் வேலை செய்வதை நிறுத்திவிட்டது. இதன் தரம் மிகவும் மோசமானது மற்றும் மலிவானதாக உணர்கிறேன். பணத்திற்கு மதிப்பில்லை.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is extremely cheap and has a very short lifespan.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is extremely cheap and has a very short lifespan, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer states that the product is extremely cheap, implying poor value.'}]}",
    },
    {
        "review": "இது என் போனை நம்பமுடியாத அளவிற்கு மெதுவாக சார்ஜ் செய்கிறது. என் பழைய சார்ஜர் இதைவிட வேகமாக இருந்தது. பணமும் நேரமும் வீண்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is a waste of money and not worth the cost.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions the product is a waste of money, implying poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer feels the product is not worth the cost, indicating poor value.'}]}",
    },
    {
        "review": "பேக்கேஜிங் நன்றாக இருந்தது, ஆனால் சார்ஜர் பயன்படுத்தும்போது ஆபத்தான முறையில் சூடாகிறது. தனியாக விட்டுச் செல்ல பயமாக இருக்கிறது. ஒரு பெரிய பாதுகாப்பு கவலை.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Generally positive experience with some minor issues.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "மெதுவான சார்ஜிங் பிரச்சினை பற்றி அவர்களின் ஆதரவுக் குழுவைத் தொடர்பு கொள்ள முயற்சித்தேன், ஆனால் எந்த பதிலும் வரவில்லை. மிகவும் மோசமான வாடிக்கையாளர் சேவை.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer had a very poor experience with the product, mentioning that the seller is unresponsive and the product is not working.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentioned that the product is not working, indicating a quality issue.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer mentioned that the seller is unresponsive, indicating poor support.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "இது வேலை செய்கிறது, ஆனால் கேபிள் மிகவும் குட்டையாக உள்ளது. இந்த விலைக்கு, நான் இன்னும் கணிசமான ஒன்றை எதிர்பார்த்தேன். இது ஒரு சராசரி, அதிக விலை கொண்ட தயாரிப்பு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is somewhat satisfied with the product, but has some reservations about its quality.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer mentions that the product is 'tiny' and 'not as advertised', indicating some quality issues.'}, {'name': 'Sizing', 'rating': 1, 'justification': 'The reviewer states that the product is 'tiny', indicating a negative experience with the size.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 2, 'justification': 'The reviewer mentions that the product is 'cheap', indicating a negative assessment of its value.'}]}",
    },
    {
        "review": "விளம்பரப்படுத்தியபடி இது வேகமான சார்ஜர் அல்ல. ஒரு நல்ல சார்ஜ் பெற பல மணிநேரம் ஆகும். நான் முற்றிலும் தவறாக வழிநடத்தப்பட்டதாக உணர்கிறேன். மதிப்பு இல்லை.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is a scam and not worth the money.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is a scam, implying poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer states that the product is not worth the money.'}]}",
    },
    {
        "review": "சாக்கெட்டில் செல்லும் முனைகள் சில பயன்பாடுகளுக்குப் பிறகு வளைந்துவிட்டன. பயன்படுத்தப்படும் பொருட்கள் தெளிவாக மிகவும் மலிவானவை. இதை யாருக்கும் பரிந்துரைக்க மாட்டேன்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive experience with the product, but some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Generally positive experience with the product, but some minor issues.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "அது வந்த பெட்டி அழகாகவும் சிறியதாகவும் இருந்தது. சார்ஜரும் சிறியது, ஆனால் சார்ஜ் செய்யும் போது ஒரு விசித்திரமான சத்தம் வருகிறது. இது கொஞ்சம் கவலையளிக்கிறது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The reviewer is generally satisfied with the product, mentioning it is 'beautiful' and 'great', but has some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'The reviewer mentions the product is 'beautiful' and 'great', indicating good quality.'}, {'name': 'Sizing', 'rating': 2, 'justification': 'The reviewer mentions the product is'small', indicating a negative aspect of sizing.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "வாங்க வேண்டாம். இந்த சார்ஜர் என் போனின் பேட்டரியை முற்றிலும் அழித்துவிட்டது. நான் ஒரு புதிய போன் வாங்க வேண்டியிருந்தது. ஆதரவைத் தொடர்பு கொள்ள முயற்சித்தேன், அவர்கள் பயனற்றவர்கள்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product due to a dead battery and poor customer support.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product has a dead battery, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer had a poor experience with customer support, as they were unable to get a replacement battery.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "கப்பல் போக்குவரத்து வேகமாகவும், பேக்கேஜிங் பாதுகாப்பாகவும் இருந்தது. சார்ஜர் எதிர்பார்த்தபடி வேலை செய்கிறது, இருப்பினும் என் போனுடன் வந்ததைப் போல பிரீமியமாக உணரவில்லை.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'The reviewer is satisfied with the product, but had some issues with the packaging.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Not mentioned in the review.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 2, 'justification': 'The reviewer had some issues with the packaging, specifically the packaging was not secure.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "சுவர் சாக்கெட்டில் இது மிகவும் இறுக்கமாக பொருந்துகிறது, மேலும் இது என் அவுட்லெட்டை உடைத்துவிடும் என்று நான் கவலைப்படுகிறேன். ஒட்டுமொத்த வடிவமைப்பு மோசமாக சிந்திக்கப்பட்டதாக உணர்கிறது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product is of poor quality, specifically the fabric is stiff and the holes are a major issue.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "ஒரு வாரத்திற்குப் பிறகு முற்றிலும் வேலை செய்வதை நிறுத்தியது. குப்பையில் எறிந்தேன். இந்த குப்பையில் உங்கள் பணத்தை வீணாக்காதீர்கள். தரம் மோசம்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is completely useless and has stopped working after a short period.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product stopped working after a short period, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "இந்த விலைக்கு, இது பரவாயில்லை என்று நினைக்கிறேன். ஆனால் இது நிச்சயமாக 'வேகமான சார்ஜிங்' என்ற கூற்றுகளுக்கு ஏற்ப வாழவில்லை. இது சுமாரானது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 3, 'justification': 'The reviewer finds the product to be average, but not terrible.'}, {'name': 'Quality', 'rating': 3, 'justification': 'The reviewer finds the product to be average, but not terrible.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 3, 'justification': 'The reviewer finds the product to be average, implying a fair value for the price.'}]}",
    },
    {
        "review": "இண்டிகேட்டர் லைட் மிகவும் பிரகாசமாக உள்ளது. நான் இரவில் அதை மூட வேண்டும். இது ஒரு சிறிய எரிச்சல், ஆனால் இது வடிவமைப்பில் விவரங்களுக்கு கவனம் இல்லாததைக் காட்டுகிறது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is somewhat satisfied with the product but has some reservations.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer mentions that the product is 'glorious' but also mentions that it is 'crazy'.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 4, 'justification': 'The reviewer mentions that the product is 'glorious' and 'crazy'.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "தயாரிப்பில் எனக்கு ஒரு சிக்கல் இருந்தது, ஆதரவுக் குழு உதவிகரமாக இல்லை மற்றும் முரட்டுத்தனமாக இருந்தது. இந்த வாங்குதலுக்கு நான் மிகவும் வருந்துகிறேன்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, mentioning several issues and a lack of support.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions several issues with the product, including a damaged product and a lack of support.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer mentions a lack of support, implying poor customer service.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "எனக்கு ஒரு நல்ல சார்ஜர் கிடைத்திருக்க வேண்டும், ஏனெனில் என்னுடையது சரியாக வேலை செய்கிறது. இது என் போனை விரைவாக சார்ஜ் செய்கிறது மற்றும் அதிக வெப்பமடையாது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The product works well.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "தரம் அங்கே இல்லை. பிளாஸ்டிக் உடையக்கூடியதாக உணர்கிறது, நான் அதை கைவிட்டால் அது விரிசல் விடும் என்று நான் உறுதியாக நம்புகிறேன். ஒரு நீடித்த தயாரிப்பு அல்ல.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is fragile and has a flaw that can be easily damaged.'}, {'name': 'Sizing', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Packaging', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Support', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Description', 'justification': 'Not mentioned in the review.', 'rating': 0}, {'name': 'Value', 'justification': 'Not mentioned in the review.', 'rating': 0}]}",
    },
    {
        "review": "இந்த சார்ஜர் ஒரு நகைச்சுவை. என் லேப்டாப்பின் USB போர்ட்டைப் பயன்படுத்துவதை விட என் போனை சார்ஜ் செய்ய அதிக நேரம் ஆகும். ஒரு பயங்கரமான மதிப்பு முன்மொழிவு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is 'irritable' and has a 'flicker' of a feature, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "பேக்கேஜிங் நேர்த்தியானது, ஆனால் செயல்திறன் இல்லை. இது வேலையைச் செய்கிறது, ஆனால் மிகவும் மெதுவாக. நான் அதை மீண்டும் வாங்க மாட்டேன்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The product is functional but has some issues with speed and performance.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The product is functional but has some issues with speed and performance.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "இது எவ்வளவு சூடாகிறது என்பது பற்றி நான் மிகவும் கவலைப்படுகிறேன். இது பாதுகாப்பானதாகத் தெரியவில்லை. உருவாக்கத் தரம் மலிவானதாகவும் இலகுவாகவும் உணர்கிறது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is 'frosty' and'sucks.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "நான் பயன்படுத்தும் போது இந்த சார்ஜரில் செருகப்பட்டிருக்கும் போது என் போன் உண்மையில் சார்ஜ் இழக்கிறது. இது முற்றிலும் பயனற்றது. தரம் குறைவு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is completely dead, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "இது ஒரு கண்ணியமான காப்பு சார்ஜர். பயணத்திற்கு அளவு வசதியானது. பேக்கேஜிங் குறைவாக இருந்தது, அதை நான் பாராட்டுகிறேன்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 5, 'justification': 'The reviewer is very satisfied with the product.'}, {'name': 'Quality', 'rating': 5, 'justification': 'The reviewer mentions that the product is of good quality.'}, {'name': 'Sizing', 'rating': 5, 'justification': 'The reviewer mentions that the product is the right size.'}, {'name': 'Packaging', 'rating': 5, 'justification': 'The reviewer mentions that the product is well packaged.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "கேபிள் இரண்டு வாரங்களுக்குப் பிறகு இணைப்புப் புள்ளியில் உடையத் தொடங்கியது. மோசமான ஆயுள் மற்றும் நிச்சயமாக விலைக்கு மதிப்பு இல்லை.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is of poor quality and has a short lifespan.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product has a short lifespan and is of poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer feels that the product is not worth the cost due to its short lifespan.'}]}",
    },
    {
        "review": "அவர்களின் வாடிக்கையாளர் ஆதரவு ஒரு கருந்துளை. மின்னஞ்சல்களுக்கு பதிலளிக்கப்படவில்லை. உங்களுக்கு ஒரு சிக்கல் இருந்தால் எந்த உதவியையும் எதிர்பார்க்க வேண்டாம். தயாரிப்பு தரம் குறைந்தது.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product and the seller.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The product is described as having a bad quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 1, 'justification': 'The reviewer mentions that the seller is unresponsive.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "இது படங்களில் அழகாக இருக்கிறது, ஆனால் நேரில், அது மலிவானதாக உணர்கிறது. சார்ஜிங் வேகமும் மிகவும் ஏமாற்றமளிக்கிறது. ஒரு நல்ல மதிப்பு அல்ல.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The reviewer is somewhat disappointed with the product.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The reviewer mentions that the battery is extremely low, indicating a potential quality issue.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 4, 'justification': 'The reviewer mentions that the product is 'beautifully designed'.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "இந்த சார்ஜர் என் போனின் சார்ஜிங் போர்ட்டை சேதப்படுத்தியது. மலிவான, குறைந்த தரமான தயாரிப்பு காரணமாக ஒரு விலையுயர்ந்த பழுது. எல்லா விலையிலும் தவிர்க்கவும்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is a total waste of money.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product is a total waste of money, implying poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer states that the product is a total waste of money, indicating poor value.'}]}",
    },
    {
        "review": "பெட்டி தொழில் ரீதியாகத் தெரிந்தது, ஆனால் உள்ளே இருந்த தயாரிப்பு பொருந்தவில்லை. இது ஒரு மிக அடிப்படையான, மெதுவான சார்ஜர். இதே விலைக்கு நீங்கள் சிறந்தவற்றைக் காணலாம்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 2, 'justification': 'The product is not as advertised, but it is functional.'}, {'name': 'Quality', 'rating': 2, 'justification': 'The product is not as advertised, but it is functional.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "தொடர்ந்து அதிக வெப்பமடைகிறது. குளிர்விக்க நான் அதை அவிழ்க்க வேண்டும். இது நீண்ட காலத்திற்கு சார்ஜருக்கோ அல்லது என் போனுக்கோ நல்லதல்ல. மோசமான தரம்.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, calling it a 'total disaster' and stating it's 'tough as nails' but also 'tough as hell'.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions the product is 'tough as nails' but also 'tough as hell', indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
    {
        "review": "நான் இவற்றில் இரண்டை வாங்கினேன், இரண்டும் ஒரு மாதத்திற்குள் தோல்வியடைந்தன. தெளிவாக ஒரு உற்பத்தித் தரப் பிரச்சினை. பணத்திற்கு பயங்கரமான மதிப்பு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 1, 'justification': 'The reviewer is extremely dissatisfied with the product, stating it is a total waste of money and has a short lifespan.'}, {'name': 'Quality', 'rating': 1, 'justification': 'The reviewer mentions that the product has a short lifespan, indicating poor quality.'}, {'name': 'Sizing', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 1, 'justification': 'The reviewer states that the product is a total waste of money, indicating poor value.'}]}",
    },
    {
        "review": "சிறிய அளவு மட்டுமே இதில் உள்ள நல்ல விஷயம். இது என் பையில் நன்றாக பொருந்துகிறது. இருப்பினும், மெதுவான சார்ஜிங் ஒரு பெரிய குறைபாடு.",
        "generated_response": "{'aspects': [{'name': 'Overall', 'rating': 4, 'justification': 'Generally positive with some minor issues.'}, {'name': 'Quality', 'rating': 4, 'justification': 'Generally positive.'}, {'name': 'Sizing', 'rating': 4, 'justification': 'The product is compact.'}, {'name': 'Packaging', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Support', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Description', 'rating': 0, 'justification': 'Not mentioned in the review.'}, {'name': 'Value', 'rating': 0, 'justification': 'Not mentioned in the review.'}]}",
    },
]


# --- Product IDs ---
# These MUST match existing user IDs in your database if products are user-specific
# For this example, I'll assume a placeholder user ID.
# In a real scenario, you'd fetch or specify the user ID for whom to create these products.
PLACEHOLDER_USER_ID = uuid.UUID(
    "b2171a1a-9a05-43bc-a3fc-dd029d22a234"
)  # Use a valid existing user_id from your DB

PRODUCT_DEFINITIONS = [
    {
        "id": "d5835910-7d1b-44fa-8133-0e5072f8b14e",
        "name": "Premium Headphones X",
        "description": "High-fidelity over-ear headphones.",
        "reviews_data": headphone_seed_data,
    },
    {
        "id": "d651fd47-646f-46b9-b382-39102f30d5b2",
        "name": "Fast USB-C Charger",
        "description": "65W GaN fast charger.",
        "reviews_data": charger_seed_data,
    },
]


def parse_generated_response(response_str: str) -> Dict[str, Any]:
    """
    Attempts to parse the Python dict-like string from generated_response.
    Returns the parsed dict or the original string if parsing fails.
    """
    try:
        # ast.literal_eval is safer for Python-like structures if they are valid literals
        # This assumes internal quotes like "it's" are escaped as "it\\'s" in the source string
        # If not, ast.literal_eval will fail.
        temp = re.sub(r"(?<=[a-zA-Z])'(?!')(?=[a-zA-Z])", "", response_str)
        temp = temp.replace("'", '"')
        return ast.literal_eval(temp)
    except (SyntaxError, ValueError) as e_ast:
        logger.warning(
            f"ast.literal_eval failed for string: {response_str[:100]}... Error: {e_ast}. Falling back to returning raw string for JSONB."
        )
        # For JSONB, PostgreSQL might be able to ingest the string as is if it's simple enough,
        # or you might get an error if it's too malformed for JSONB's looser parsing.
        # The safest is for RunPod to provide valid JSON or valid, escaped Python literals.
        # As a last resort for JSONB, we can try to make it valid JSON string by dumping a dict containing the raw string
        return {
            "raw_unparsable_string": response_str
        }  # Store it wrapped if direct storage as JSONB fails
    except Exception as e_other:
        logger.error(
            f"Unexpected error parsing generated_response string: {e_other}. String: {response_str[:100]}...",
            exc_info=True,
        )
        return {"raw_unparsable_string": response_str, "parsing_error": str(e_other)}


@router.post("/load-sample-data", summary="Load sample products and reviews into DB")
async def load_sample_data(
    analysis_svc: AnalysisService = Depends(
        get_analysis_service_instance
    ),  # Keep if you use background_tasks
    background_tasks: BackgroundTasks = BackgroundTasks(),
    # Add auth dependency if needed: current_user: dict = Depends(get_current_admin_user)
):
    logger.info("Admin: Initiating loading of sample product and review data...")
    created_products_count = 0
    created_reviews_count = 0
    created_analysis_count = 0

    total_reviews_to_seed = sum(len(p["reviews_data"]) for p in PRODUCT_DEFINITIONS)
    review_timestamps = get_varied_past_timestamps(
        total_reviews_to_seed, days_spread=180
    )
    timestamp_idx = 0

    for product_def in PRODUCT_DEFINITIONS:
        product_id = uuid.UUID(product_def["id"])
        product_created_at = (
            review_timestamps[timestamp_idx]
            if timestamp_idx < len(review_timestamps)
            else datetime.now(timezone.utc)
        )  # Use first review's time for product for simplicity

        existing_product = db_products.get_product_by_id_db(
            product_id=product_id, user_id=PLACEHOLDER_USER_ID
        )
        if not existing_product:
            product_to_create = db_schemas.ProductCreate(
                name=product_def["name"], description=product_def["description"]
            )
            logger.info(
                f"Admin: Creating product '{product_def['name']}' (ID: {product_id}) for user {PLACEHOLDER_USER_ID} with created_at: {product_created_at}"
            )

            # Using modified create_product_db that accepts created_at
            db_product = db_products.create_product_db(
                product=product_to_create,
                user_id=PLACEHOLDER_USER_ID,
                created_at=product_created_at,  # Pass the historical timestamp
            )
            if db_product:
                created_products_count += 1
            else:
                logger.error(
                    f"Admin: Failed to create product '{product_def['name']}'. Skipping its reviews."
                )
                continue
        else:
            logger.info(
                f"Admin: Product '{product_def['name']}' (ID: {product_id}) already exists. Skipping creation."
            )

        for review_data in product_def["reviews_data"]:
            if timestamp_idx >= len(review_timestamps):
                review_created_at = datetime.now(timezone.utc)  # Fallback
            else:
                review_created_at = review_timestamps[timestamp_idx]
                timestamp_idx += 1

            review_to_create = db_schemas.ReviewCreate(
                review_text=review_data["review"],
                customer_id=f"customer_{random.randint(100,999)}",
            )
            logger.debug(
                f"Admin: Creating review for product {product_id}: '{review_data['review'][:30]}...' with created_at: {review_created_at}"
            )

            # Using modified create_review_db that accepts created_at
            created_review_schema: Optional[db_schemas.Review] = (
                db_reviews.create_review_db(
                    review=review_to_create,
                    product_id=product_id,
                    created_at=review_created_at,  # Pass the historical timestamp
                )
            )

            if created_review_schema and created_review_schema.id:
                created_reviews_count += 1
                logger.info(
                    f"Admin: Created review {created_review_schema.id} for product {product_id}."
                )

                # Prepare and create analysis result
                parsed_model_output_dict = parse_generated_response(
                    review_data["generated_response"]
                )

                if "error" in parsed_model_output_dict:  # Check if parsing failed
                    logger.error(
                        f"Admin: Could not parse generated_response for review {created_review_schema.id}. Error: {parsed_model_output_dict['error']}. Skipping analysis result creation."
                    )
                else:
                    analysis_to_create = db_schemas.AnalysisResultCreate(
                        review_id=created_review_schema.id,
                        result_json=parsed_model_output_dict,
                    )
                    logger.debug(
                        f"Admin: Creating analysis for review {created_review_schema.id} with created_at/updated_at: {review_created_at}"
                    )

                    # Using modified create_analysis_result_db that accepts overrides
                    created_analysis: Optional[db_schemas.AnalysisResultItem] = (
                        db_analysis_results.create_analysis_result_db(
                            result=analysis_to_create,
                            created_at_override=review_created_at,  # Use review's historical timestamp
                            updated_at_override=review_created_at,  # Use review's historical timestamp
                        )
                    )
                    if created_analysis:
                        created_analysis_count += 1
                    else:
                        logger.error(
                            f"Admin: Failed to create analysis result for review {created_review_schema.id}"
                        )

                # Optional: Trigger your actual analysis service for further processing if needed
                # This might re-analyze and overwrite the seeded analysis result if force_model_reanalysis is true in that path
                # background_tasks.add_task(
                #     analysis_svc.analyze_and_store_single_review,
                #     review_schema_item=created_review_schema,
                #     user_id_for_context=PLACEHOLDER_USER_ID
                # )
            else:
                logger.error(
                    f"Admin: Failed to create review for product {product_id}: '{review_data['review'][:30]}...'"
                )

    summary_msg = f"Sample data loading complete. Products created/checked: {len(PRODUCT_DEFINITIONS)} (newly created: {created_products_count}). Reviews created: {created_reviews_count}. Analysis results created: {created_analysis_count}."
    logger.info(summary_msg)
    return {"message": summary_msg}
