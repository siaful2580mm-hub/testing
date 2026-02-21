import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from supabase import create_client, Client
from dotenv import load_dotenv

# .env ফাইল লোড করা (লোকাল ডেভেলপমেন্টের জন্য)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "sahityik_secret_key_2026")

# Supabase কনফিগারেশন
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ImgBB কনফিগারেশন
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"

# ----------------- রাউটস (Routes) ----------------- #

@app.route('/')
def index():
    # Supabase থেকে সব অ্যাপ্রুভড কন্টেন্ট আনা
    try:
        response = supabase.table('contents').select('*, categories(name_bn)').eq('is_approved', True).order('created_at', desc=True).execute()
        contents = response.data
    except Exception as e:
        contents = []
        print("Database Error:", e)
    
    return render_template('index.html', contents=contents)


@app.route('/content/<slug>')
def single_content(slug):
    # নির্দিষ্ট Slug দিয়ে কন্টেন্ট আনা
    response = supabase.table('contents').select('*, categories(name_bn)').eq('slug', slug).execute()
    if not response.data:
        abort(404)
    content = response.data[0]
    return render_template('single.html', content=content)


@app.route('/upload', methods=['GET', 'POST'])
def upload_content():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        slug = request.form.get('slug')
        alt_text = request.form.get('alt_text')
        category_id = request.form.get('category_id')
        file = request.files.get('file')

        if not file:
            flash("দয়া করে একটি ফাইল নির্বাচন করুন।", "error")
            return redirect(request.url)

        # ImgBB তে ছবি আপলোড
        try:
            payload = {'key': IMGBB_API_KEY}
            files = {'image': file.read()}
            imgbb_response = requests.post(IMGBB_UPLOAD_URL, params=payload, files=files)
            imgbb_data = imgbb_response.json()

            if imgbb_response.status_code == 200 and imgbb_data['success']:
                file_url = imgbb_data['data']['url']
            else:
                flash("ছবি আপলোডে সমস্যা হয়েছে।", "error")
                return redirect(request.url)

            # Supabase এ ডাটা সেভ করা
            new_content = {
                "user_id": "DEFAULT_USER_ID", # বাস্তবে এটি লগইন সেশন থেকে আসবে
                "title": title,
                "description": description,
                "slug": slug,
                "alt_text": alt_text,
                "category_id": category_id,
                "file_url": file_url,
                "is_approved": True # প্রজেক্ট টেস্টিংয়ের জন্য সরাসরি ট্রু রাখা হলো
            }
            supabase.table('contents').insert(new_content).execute()
            
            flash("কন্টেন্ট সফলভাবে আপলোড হয়েছে!", "success")
            return redirect(url_for('index'))

        except Exception as e:
            flash(f"একটি ত্রুটি ঘটেছে: {str(e)}", "error")
            return redirect(request.url)

    # ফর্ম দেখানোর জন্য ক্যাটাগরি ফেচ
    categories = supabase.table('categories').select('*').execute().data
    return render_template('upload.html', categories=categories)


# শুধুমাত্র লোকাল টেস্টের জন্য, Vercel এটি ইগনোর করবে
if __name__ == '__main__':
    app.run(debug=True, port=5000)
