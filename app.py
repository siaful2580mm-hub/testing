import os
import requests
import random
from datetime import timedelta  # <--- এটি নতুন ইমপোর্ট করতে হবে
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session, Response
from functools import wraps
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "sahityik_secret_key_2026")

# ==========================================
# ডাইনামিক URL জেনারেটর (টেমপ্লেটের জন্য)
# ==========================================
@app.context_processor
def utility_processor():
    def get_url(item):
        cat_slug = item.get('categories', {}).get('slug', 'image')
        if cat_slug == 'story': 
            return f"/st/{item['slug']}"
        elif cat_slug == 'blog': 
            return f"/bg/{item['slug']}"
        elif cat_slug == 'font': 
            return f"/ft/{item['slug']}" # ফন্টের জন্য /ft/
        else: 
            return f"/image/{item['slug']}"
    return dict(get_url=get_url)
    

# সেশন যেন ৩০ দিন পর্যন্ত ব্রাউজারে সেভ থাকে
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
# Supabase কনফিগারেশন
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ImgBB কনফিগারেশন
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"

# ----------------- রাউটস (Routes) ----------------- #
# ==========================================
# লগইন চেকার ডেকোরেটর (যে পেজগুলোতে লগইন ছাড়া ঢোকা যাবে না)
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("এই পেজটি ব্যবহার করার জন্য আগে লগইন করুন।", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# হোমপেজ (Landing Page)
# ==========================================
@app.route('/')
def index():
    try:
        # ডেটাবেস থেকে সব অ্যাপ্রুভড কন্টেন্ট আনা (একসাথে)
        res = supabase.table('contents').select('*, categories(name_bn, slug), profiles(username, display_name, avatar_url)').eq('is_approved', True).order('created_at', desc=True).limit(100).execute()
        all_contents = res.data
    except Exception as e:
        all_contents = []
        print("Database Error:", e)

    # পাইথনের মাধ্যমে কন্টেন্টগুলোকে ক্যাটাগরি অনুযায়ী ভাগ করা
    images = [c for c in all_contents if c['categories']['slug'] in ['image', 'poster', 'picture']][:6] # ৬টি ছবি
    stories = [c for c in all_contents if c['categories']['slug'] == 'story'][:3] # ৩টি গল্প
    fonts = [c for c in all_contents if c['categories']['slug'] == 'font'][:3]   # ৩টি ফন্ট
    blogs = [c for c in all_contents if c['categories']['slug'] == 'blog'][:3]   # ৩টি ব্লগ

    return render_template('index.html', images=images, stories=stories, fonts=fonts, blogs=blogs)
# ==========================================
# ইউজার পেআউট ও হিস্ট্রি (User Payout & History)
# ==========================================


# ==========================================
# কন্টেন্ট এডিট (Edit Content) রাউট
# ==========================================
@app.route('/edit-content/<int:content_id>', methods=['GET', 'POST'])
@login_required
def edit_content(content_id):
    # ডেটাবেস থেকে কন্টেন্ট এবং তার ক্যাটাগরি ফেচ করা
    res = supabase.table('contents').select('*, categories(slug)').eq('id', content_id).execute().data
    if not res:
        abort(404)
        
    content = res[0]
    cat_slug = content['categories']['slug']
    
    # সিকিউরিটি চেক: শুধুমাত্র কন্টেন্টের মালিক এডিট করতে পারবে
    if content['user_id'] != session['user']['id']:
        flash("আপনি এই কন্টেন্টটি এডিট করার অনুমতি রাখেন না!", "error")
        return redirect(request.referrer or '/')

    if request.method == 'POST':
        update_data = {
            "title": request.form.get('title'),
            "description": request.form.get('description')
        }
        
        # যদি গল্প বা ব্লগ হয়, তবে এই এক্সট্রা ফিল্ডগুলো আপডেট হবে
        if cat_slug in ['story', 'blog']:
            update_data["body_text"] = request.form.get('body_text')
            update_data["next_part_link"] = request.form.get('next_part_link')
            update_data["genre"] = request.form.get('genre')
            update_data["is_original"] = True if request.form.get('is_original') == 'true' else False

        # Supabase এ আপডেট করা
        supabase.table('contents').update(update_data).eq('id', content_id).execute()
        flash("কন্টেন্ট সফলভাবে আপডেট হয়েছে!", "success")
        
        # ক্যাটাগরি অনুযায়ী সঠিক লিংকে ফেরত পাঠানো (Redirect)
        prefix = '/st/' if cat_slug == 'story' else '/bg/' if cat_slug == 'blog' else '/ft/' if cat_slug == 'font' else '/image/'
        return redirect(f"{prefix}{content['slug']}")

    return render_template('edit_content.html', content=content, cat_slug=cat_slug)
    # ==========================================
# গ্র্যান্ড ওপেনিং (Grand Opening / Welcome Page)
# ==========================================
@app.route('/grand-opening')
def grand_opening():
    # URL থেকে নাম রিসিভ করা (যেমন: /grand-opening?id=sadiya)
    guest_name = request.args.get('id', '')
    if guest_name:
        guest_name = guest_name.capitalize() # নামের প্রথম অক্ষর বড় হাতের করবে

    # গ্যালারির জন্য কয়েকটি লেটেস্ট ছবি ফেচ করা
    res = supabase.table('contents').select('*, categories(name_bn, slug), profiles(username, display_name)').eq('is_approved', True).order('created_at', desc=True).limit(4).execute()
    images = res.data if res.data else[]

    return render_template('grand_opening.html', guest_name=guest_name, images=images)
    
@app.route('/payout', methods=['GET', 'POST'])
@login_required
def payout_history():
    user_id = session['user']['id']
    
    # ১. মোট আয় হিসাব করা
    res = supabase.table('contents').select('views, downloads').eq('user_id', user_id).eq('is_approved', True).execute()
    total_earnings = sum([(item.get('views', 0) * 0.4) + (item.get('downloads', 0) * 0.5) for item in res.data])
    
    # ২. মোট উত্তোলিত বা পেন্ডিং পেমেন্ট হিসাব করা
    payouts_res = supabase.table('payouts').select('amount, status').eq('user_id', user_id).in_('status', ['Pending', 'Approved']).execute()
    total_withdrawn = sum([p['amount'] for p in payouts_res.data])
    
    # ৩. বর্তমান এভেইলেবল ব্যালেন্স
    available_balance = round(total_earnings - total_withdrawn, 2)
    
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        payment_method = request.form.get('payment_method')
        account_info = request.form.get('account_info')
        
        if amount < 50:
            flash("সর্বনিম্ন ৫০ টাকা উত্তোলন করা যাবে।", "error")
        elif amount > available_balance:
            flash("আপনার অ্যাকাউন্টে পর্যাপ্ত ব্যালেন্স নেই!", "error")
        else:
            supabase.table('payouts').insert({
                'user_id': user_id,
                'amount': amount,
                'payment_method': payment_method,
                'account_info': account_info
            }).execute()
            flash("আপনার উত্তোলনের অনুরোধটি সফলভাবে জমা হয়েছে। অ্যাডমিন শীঘ্রই পেমেন্ট করে দিবে।", "success")
            return redirect(url_for('payout_history'))
            
    # ইউজারের পেআউট হিস্ট্রি ফেচ করা
    history = supabase.table('payouts').select('*').eq('user_id', user_id).order('created_at', desc=True).execute().data
    
    return render_template('payout.html', available_balance=available_balance, history=history)


# ==========================================
# সাইনআপ (Registration) রাউট
# ==========================================

# ==========================================
# পাবলিক প্রোফাইল ভিউ (ইউজারের সব ইনফো এবং আপলোড করা ছবি দেখাবে)
# ==========================================
# ==========================================
# পাবলিক প্রোফাইল ভিউ (ফলো সিস্টেম সহ)
# ==========================================
# ==========================================
# ফলো / আনফলো রাউট (Follow/Unfollow)
# ==========================================
@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow_user(username):
    # যাকে ফলো করবে তার আইডি বের করা
    target_user = supabase.table('profiles').select('id').eq('username', username).execute().data
    if not target_user:
        abort(404)
        
    follower_id = session['user']['id']
    following_id = target_user[0]['id']

    if follower_id == following_id:
        flash("আপনি নিজেকে ফলো করতে পারবেন না!", "error")
        return redirect(request.referrer)

    # আগে থেকেই ফলো করা আছে কিনা চেক করা
    check = supabase.table('followers').select('*').eq('follower_id', follower_id).eq('following_id', following_id).execute().data
    
    if check:
        # আনফলো লজিক
        supabase.table('followers').delete().eq('follower_id', follower_id).eq('following_id', following_id).execute()
        flash(f"আপনি {username} কে আনফলো করেছেন।", "success")
    else:
        # ফলো লজিক
        supabase.table('followers').insert({"follower_id": follower_id, "following_id": following_id}).execute()
        flash(f"আপনি {username} কে ফলো করেছেন!", "success")

    return redirect(request.referrer)
# ==========================================
# ডেডিকেটেড গ্যালারি / ক্যাটাগরি পেজ
# ==========================================
@app.route('/c/<category_slug>')
def category_page(category_slug):
    # ১. ক্যাটাগরির তথ্য বের করা
    cat_res = supabase.table('categories').select('*').eq('slug', category_slug).execute()
    if not cat_res.data:
        abort(404)
    category = cat_res.data[0]

    # ২. এই ক্যাটাগরির সব অ্যাপ্রুভড কন্টেন্ট ফেচ করা
    contents_res = supabase.table('contents').select('*, categories(name_bn, slug), profiles(username, display_name, avatar_url)').eq('category_id', category['id']).eq('is_approved', True).order('created_at', desc=True).execute()
    contents = contents_res.data

    return render_template('category.html', category=category, contents=contents)

# ==========================================
# ইনসাইট ও আয় (Insight & Earning) রাউট
# ==========================================
@app.route('/insight')
@login_required
def user_insight():
    user_id = session['user']['id']
    
    # ইউজারের আপলোড করা সব কন্টেন্ট ফেচ করা
    res = supabase.table('contents').select('title, slug, views, downloads, file_url, is_approved, created_at, categories(slug)').eq('user_id', user_id).order('created_at', desc=True).execute()
    contents = res.data

    total_views = 0
    total_downloads = 0
    total_earnings = 0.0

    # আয়ের হিসাব (Calculation)
    for item in contents:
        v = item.get('views') or 0
        d = item.get('downloads') or 0
        
        # প্রতি ভিউ ০.৪ টাকা, প্রতি ডাউনলোড ০.৫ টাকা
        earning = (v * 0.4) + (d * 0.5)
        
        item['views'] = v
        item['downloads'] = d
        item['earning'] = round(earning, 2) # দশমিকের পর ২ ঘর পর্যন্ত রাখা
        
        if item.get('is_approved'):
            total_views += v
            total_downloads += d
            total_earnings += earning

    total_earnings = round(total_earnings, 2)

    return render_template('insight.html', contents=contents, total_views=total_views, total_downloads=total_downloads, total_earnings=total_earnings)
# ==========================================
# আমাদের সম্পর্কে (About Us) পেজ
# ==========================================
@app.route('/about')
def about():
    return render_template('about.html')
# ==========================================
# সিঙ্গেল ইমেজ/কন্টেন্ট ডিটেইলস পেজ
# ==========================================
@app.route('/image/<slug>')
@app.route('/st/<slug>')
@app.route('/bg/<slug>')
@app.route('/ft/<slug>')
def single_content(slug):
    # ১. কন্টেন্ট ফেচ করা (categories(name_bn, slug) যুক্ত করা হয়েছে)
    res = supabase.table('contents').select('*, categories(name_bn, slug), profiles(username, display_name, avatar_url)').eq('slug', slug).execute()
    if not res.data:
        abort(404)
    
    content = res.data[0]
    content_id = content['id']
# ২. স্মার্ট ভিউ (View) কাউন্টার (৭৫% কাউন্ট হবে, ২৫% স্কিপ হবে)
    viewed_items = session.get('viewed_items', [])
    
    if content_id not in viewed_items:
        # random.random() ০ থেকে ১ এর মধ্যে একটি সংখ্যা দেয়। 
        # যদি সংখ্যাটি 0.75 এর নিচে হয় (অর্থাৎ ৭৫% সম্ভাবনা), তবেই ভিউ কাউন্ট হবে
        if random.random() < 0.75:
            new_views = content.get('views', 0) + 1
            supabase.table('contents').update({'views': new_views}).eq('id', content_id).execute()
            content['views'] = new_views # পেজে দেখানোর জন্য আপডেট করা হলো
        else:
            # ২৫% সম্ভাবনা: ভিউ কাউন্ট হবে না, স্কিপ করবে।
            pass 
        
        # ভিউ কাউন্ট হোক বা স্কিপ হোক— আমরা সেশনে সেভ করে রাখব। 
        # এতে করে যে ২৫% স্কিপ হয়েছে, সে যদি বারবার রিফ্রেশও দেয়, তবুও তার ভিউ আর কাউন্ট হবে না!
        viewed_items.append(content_id)
        session['viewed_items'] = viewed_items
        session.modified = True
    else:
        # আগে থেকেই দেখা থাকলে কোনো ডেটাবেস আপডেট হবে না
        pass

    # ৩. লাইক (Like) কাউন্ট এবং চেক করা
    likes_res = supabase.table('likes').select('id', count='exact').eq('content_id', content_id).execute()
    likes_count = likes_res.count if likes_res.count else 0

    user_liked = False
    if 'user' in session:
        check_like = supabase.table('likes').select('*').eq('content_id', content_id).eq('user_id', session['user']['id']).execute()
        if check_like.data:
            user_liked = True

    # ৪. কমেন্টস (Comments) ফেচ করা
    comments = supabase.table('comments').select('*, profiles(username, display_name, avatar_url)').eq('content_id', content_id).order('created_at', desc=True).execute().data

    # ৫. রিলেটেড কন্টেন্ট (একই ক্যাটাগরির অন্য ছবি/গল্প)
    # এখানেও categories(name_bn, slug) দেওয়া হয়েছে, যাতে লিংকে কোনো এরর না আসে
    related = supabase.table('contents').select('*, categories(name_bn, slug), profiles(username, display_name)').eq('category_id', content['category_id']).eq('is_approved', True).neq('id', content_id).limit(4).execute().data

    # ৬. ক্যাটাগরি চেক করে আলাদা টেমপ্লেট রেন্ডার করা
    cat_slug = content['categories']['slug']
    
    if cat_slug in ['story', 'blog']:
        # গল্প এবং ব্লগের জন্য আলাদা রিডিং টেমপ্লেট
        return render_template('story_single.html', content=content, likes_count=likes_count, user_liked=user_liked, comments=comments, related=related)
    else:
        # ছবি, পোস্টার এবং ফন্টের জন্য গ্যালারি টেমপ্লেট
        return render_template('single.html', content=content, likes_count=likes_count, user_liked=user_liked, comments=comments, related=related)
@app.route('/p/<username>')
def user_profile(username):
    user_res = supabase.table('profiles').select('*').eq('username', username).execute()
    if not user_res.data:
        abort(404)
    profile_data = user_res.data[0]
    
    # আপলোড করা ছবি ফেচ
    contents_res = supabase.table('contents').select('*, categories(name_bn)').eq('user_id', profile_data['id']).eq('is_approved', True).order('created_at', desc=True).execute()
    uploaded_contents = contents_res.data

    # --- ফলো সিস্টেম লজিক ---
    is_following = False
    followers_list = []
    
    # মোট ফলোয়ার গণনা
    followers_count_res = supabase.table('followers').select('id', count='exact').eq('following_id', profile_data['id']).execute()
    followers_count = followers_count_res.count if followers_count_res.count else 0

    if 'user' in session:
        # চেক করুন বর্তমান ইউজার এই প্রোফাইলকে ফলো করে কিনা
        check = supabase.table('followers').select('*').eq('follower_id', session['user']['id']).eq('following_id', profile_data['id']).execute()
        if check.data:
            is_following = True

        # যদি ইউজার তার নিজের প্রোফাইলে থাকে, তবে ফলোয়ারদের লিস্ট বের করা
        if session['user']['id'] == profile_data['id']:
            followers_data = supabase.table('followers').select('follower_id').eq('following_id', profile_data['id']).execute().data
            follower_ids = [f['follower_id'] for f in followers_data]
            if follower_ids:
                followers_list = supabase.table('profiles').select('username, display_name, avatar_url').in_('id', follower_ids).execute().data

    return render_template('profile.html', profile=profile_data, contents=uploaded_contents, is_following=is_following, followers_count=followers_count, followers_list=followers_list)
# ==========================================
# প্রোফাইল এডিট/আপডেট রাউট (লগইন করা ইউজার নিজের ডাটা আপডেট করবে)
# ==========================================
@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user_id = session['user']['id']

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        display_name = request.form.get('display_name')
        bio = request.form.get('bio')
        fb_page_link = request.form.get('fb_page_link')
        fb_group_link = request.form.get('fb_group_link')
        pinterest_link = request.form.get('pinterest_link')
        tiktok_link = request.form.get('tiktok_link')
        contact_info = request.form.get('contact_info')
        
        # ডিফল্ট ডাটা ডিকশনারি
        update_data = {
            "full_name": full_name,
            "display_name": display_name,
            "bio": bio,
            "fb_page_link": fb_page_link,
            "fb_group_link": fb_group_link,
            "pinterest_link": pinterest_link,
            "tiktok_link": tiktok_link,
            "contact_info": contact_info
        }

        # যদি ইউজার নতুন প্রোফাইল ছবি দেয়, তবে ImgBB তে আপলোড করা
        file = request.files.get('avatar')
        if file and file.filename != '':
            try:
                payload = {'key': IMGBB_API_KEY}
                files = {'image': file.read()}
                imgbb_res = requests.post(IMGBB_UPLOAD_URL, params=payload, files=files).json()
                
                if imgbb_res.get('success'):
                    update_data['avatar_url'] = imgbb_res['data']['url']
            except Exception as e:
                flash("প্রোফাইল ছবি আপলোডে সমস্যা হয়েছে।", "error")

        # Supabase এ প্রোফাইল আপডেট
        supabase.table('profiles').update(update_data).eq('id', user_id).execute()
        flash("আপনার প্রোফাইল সফলভাবে আপডেট হয়েছে!", "success")
        return redirect(url_for('user_profile', username=session['user']['username']))

    # GET Request: ফর্ম দেখানোর জন্য বর্তমান ডাটা ফেচ
    current_profile = supabase.table('profiles').select('*').eq('id', user_id).execute().data[0]
    return render_template('edit_profile.html', profile=current_profile)
# ==========================================
# সাইনআপ (Registration) রাউট
# ==========================================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        display_name = request.form.get('display_name') # ইউজারের আসল নাম (বাংলা বা স্পেসযুক্ত)
        username = request.form.get('username')         # প্রোফাইল লিংকের জন্য ইউজারনেম
        email = request.form.get('email')
        password = request.form.get('password')
        
        # ইউজারনেমটি লিংকের জন্য পারফেক্ট করা (সব ছোট হাতের এবং স্পেস রিমুভ করা)
        username = username.lower().replace(" ", "")

        try:
            # Supabase এ নতুন ইউজার তৈরি
            res = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "username": username,
                        "display_name": display_name
                    }
                }
            })
            flash("রেজিস্ট্রেশন সফল হয়েছে! দয়া করে লগইন করুন।", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"ত্রুটি: {str(e)}", "error")
            return redirect(request.url)

    return render_template('signup.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Supabase Auth দিয়ে লগইন চেক
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            
            # সেশনকে ব্রাউজারে স্থায়ী (Permanent) করা
            session.permanent = True  # <--- এই লাইনটি যুক্ত করতে হবে
            
            # ফ্লাস্ক সেশনে ইউজারের তথ্য সেভ করে রাখা
            session['user'] = {
                "id": res.user.id,
                "email": res.user.email,
                "username": res.user.user_metadata.get('username', 'সাহিত্যিক')
            }
            session['access_token'] = res.session.access_token
            
            flash(f"স্বাগতম, {session['user']['username']}!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash("ইমেইল বা পাসওয়ার্ড ভুল হয়েছে!", "error")
            return redirect(request.url)

    return render_template('login.html')
# ==========================================
# লগআউট (Logout) রাউট
# ==========================================
@app.route('/logout')
def logout():
    session.clear() # সেশন ক্লিয়ার করে দেওয়া
    supabase.auth.sign_out()
    flash("আপনি সফলভাবে লগআউট হয়েছেন।", "success")
    return redirect(url_for('login'))



# ==========================================
# লাইক, কমেন্ট এবং ডাউনলোড অ্যাকশন রাউটস
# ==========================================
@app.route('/like/<int:content_id>', methods=['POST'])
@login_required
def like_content(content_id):
    user_id = session['user']['id']
    check = supabase.table('likes').select('*').eq('content_id', content_id).eq('user_id', user_id).execute().data
    
    if check:
        supabase.table('likes').delete().eq('content_id', content_id).eq('user_id', user_id).execute() # আনলাইক
    else:
        supabase.table('likes').insert({'content_id': content_id, 'user_id': user_id}).execute() # লাইক
    return redirect(request.referrer)

@app.route('/comment/<int:content_id>', methods=['POST'])
@login_required
def add_comment(content_id):
    text = request.form.get('text')
    if text:
        supabase.table('comments').insert({'content_id': content_id, 'user_id': session['user']['id'], 'text': text}).execute()
        flash('আপনার মন্তব্য যুক্ত হয়েছে।', 'success')
    return redirect(request.referrer)

# ==========================================
# ফোর্স ডাউনলোড (Force Download) রাউট
# ==========================================
@app.route('/download/<int:content_id>')
def download_content(content_id):
    # ডেটাবেস থেকে ছবির তথ্য বের করা
    res = supabase.table('contents').select('title, slug, file_format, downloads, file_url').eq('id', content_id).execute().data
    if not res:
        abort(404)

    content = res[0]
    
    # ১. ডাউনলোড কাউন্ট বাড়ানো
    current_dl = content.get('downloads', 0)
    supabase.table('contents').update({'downloads': current_dl + 1}).eq('id', content_id).execute()

    # ২. ছবিটির লিংক এবং সুন্দর একটি ফাইলের নাম তৈরি করা (যেমন: ekusher-bhor.jpg)
    file_url = content['file_url']
    file_format = content.get('file_format', 'jpg').lower()
    filename = f"{content['slug']}.{file_format}"

    try:
        # requests দিয়ে ImgBB থেকে ছবিটি ব্যাকএন্ডে নিয়ে আসা
        r = requests.get(file_url, stream=True)
        
        # Response তৈরি করে Content-Disposition 'attachment' দেওয়া, যাতে সরাসরি ডাউনলোড শুরু হয়
        return Response(
            r.iter_content(chunk_size=1024 * 1024), # 1MB চাঙ্ক হিসেবে ডাউনলোড হবে
            content_type=r.headers.get('Content-Type', 'image/jpeg'),
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        flash("ডাউনলোড করতে সমস্যা হচ্ছে। দয়া করে আবার চেষ্টা করুন।", "error")
        return redirect(request.referrer)

# ==========================================
# আপলোড হাব (Upload Hub) - অপশন সিলেক্ট করার পেজ
# ==========================================
@app.route('/upload')
@login_required
def upload_hub():
    return render_template('upload.html')
# ==========================================
# নির্দিষ্ট ক্যাটাগরির আপলোড ফর্ম (Dynamic Upload Form)
# ==========================================
@app.route('/upload/<upload_type>', methods=['GET', 'POST'])
@login_required
def upload_content(upload_type):
    # ১. ভ্যালিড টাইপ চেক করা
    valid_types = ['image', 'story', 'font', 'blog']
    if upload_type not in valid_types:
        abort(404)

    # ২. ডেটাবেস থেকে ক্যাটাগরির ID বের করা
    try:
        category_res = supabase.table('categories').select('id, name_bn').eq('slug', upload_type).execute()
        if not category_res.data:
            flash("এই ক্যাটাগরিটি এখনো তৈরি করা হয়নি!", "error")
            return redirect(url_for('upload_hub'))
        
        category_id = category_res.data[0]['id']
        category_name = category_res.data[0]['name_bn']
    except Exception as e:
        flash("ডেটাবেস কানেকশনে সমস্যা হচ্ছে।", "error")
        return redirect(url_for('upload_hub'))

    # ৩. ফর্ম সাবমিট হলে (POST Request)
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        slug = request.form.get('slug')
        alt_text = request.form.get('alt_text')
        genre = request.form.get('genre')  # ছবি বা গল্পের সাব-ক্যাটাগরি

        # ৩টি হ্যাশট্যাগ রিসিভ করে ক্লিন করা এবং একসাথে কমা (,) দিয়ে যুক্ত করা
        h1 = request.form.get('hashtag1', '').strip().replace('#', '')
        h2 = request.form.get('hashtag2', '').strip().replace('#', '')
        h3 = request.form.get('hashtag3', '').strip().replace('#', '')
        hashtags_list = [h for h in[h1, h2, h3] if h]  # যেগুলো ফাঁকা সেগুলো বাদ যাবে
        hashtags_str = ",".join(hashtags_list)

        file = request.files.get('file')

        if not file:
            flash("দয়া করে একটি ছবি বা ফাইল নির্বাচন করুন।", "error")
            return redirect(request.url)

        try:
            # ImgBB-তে ছবি আপলোড করা
            payload = {'key': IMGBB_API_KEY}
            files = {'image': file.read()}
            imgbb_response = requests.post(IMGBB_UPLOAD_URL, params=payload, files=files)
            imgbb_data = imgbb_response.json()

            if imgbb_response.status_code == 200 and imgbb_data['success']:
                file_url = imgbb_data['data']['url']
            else:
                flash("ছবি আপলোডে সমস্যা হয়েছে। দয়া করে আবার চেষ্টা করুন।", "error")
                return redirect(request.url)

            # ফাইল ফরম্যাট বের করা (যেমন: JPG, PNG)
            file_format = file.filename.rsplit('.', 1)[1].upper() if '.' in file.filename else 'JPG'

            # Supabase-এ সেভ করার জন্য ডেটার ডিকশনারি তৈরি
            new_content = {
                "user_id": session['user']['id'],
                "title": title,
                "description": description,
                "slug": slug,
                "alt_text": alt_text,
                "category_id": category_id,
                "file_url": file_url,
                "file_format": file_format,
                "genre": genre,
                "hashtags": hashtags_str,
                "is_approved": False  # অ্যাডমিন প্যানেল থেকে অ্যাপ্রুভ করতে হবে
            }

            # যদি গল্প বা ব্লগ হয়, তবে অতিরিক্ত ডেটাগুলো যুক্ত হবে
            if upload_type in['story', 'blog']:
                new_content['body_text'] = request.form.get('body_text')
                new_content['next_part_link'] = request.form.get('next_part_link')
                new_content['is_original'] = True if request.form.get('is_original') == 'true' else False

            # ডেটাবেসে ইনসার্ট (Insert) করা
            supabase.table('contents').insert(new_content).execute()
            
            flash(f"আপনার {category_name} সফলভাবে আপলোড হয়েছে এবং অনুমোদনের অপেক্ষায় আছে!", "success")
            return redirect(url_for('index'))

        except Exception as e:
            # কোনো এরর আসলে ইউজারকে মেসেজ দেখাবে
            flash(f"একটি ত্রুটি ঘটেছে: {str(e)}", "error")
            return redirect(request.url)

    # ৪. GET Request এর জন্য ফর্ম পেজ রেন্ডার করা
    return render_template('upload_form.html', upload_type=upload_type, category_id=category_id, category_name=category_name)
    
# ==========================================
# লগআউট (Logout) রাউট
# ==========================================

# ==========================================
# অ্যাডমিন চেকার ডেকোরেটর
# ==========================================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # যদি ইউজার লগইন করা না থাকে অথবা ইমেইল admin@gmail.com না হয়
        if 'user' not in session or session['user']['email'] != 'admin@gmail.com':
            flash("এই পেজে প্রবেশের অনুমতি আপনার নেই!", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# অ্যাডমিন প্যানেল রাউটস (Admin Panel)
# ==========================================
# ==========================================
# অ্যাডমিন প্যানেল রাউটস (Admin Panel)
# ==========================================
@app.route('/admin')
@admin_required
def admin_panel():
    # ১. যেসব কন্টেন্ট এখনো অ্যাপ্রুভ হয়নি (Pending)
    pending_res = supabase.table('contents').select('*, categories(name_bn, slug), profiles(username, display_name)').eq('is_approved', False).order('created_at', desc=True).execute()
    
    # ২. যেসব কন্টেন্ট ইতোমধ্যে পাবলিশ হয়েছে (Approved)
    approved_res = supabase.table('contents').select('*, categories(name_bn, slug), profiles(username, display_name)').eq('is_approved', True).order('created_at', desc=True).execute()
    
    return render_template('admin.html', pending_contents=pending_res.data, approved_contents=approved_res.data)

@app.route('/admin/approve/<int:id>')
@admin_required
def approve_content(id):
    # কন্টেন্ট অ্যাপ্রুভ করা
    supabase.table('contents').update({'is_approved': True}).eq('id', id).execute()
    flash('কন্টেন্ট সফলভাবে অ্যাপ্রুভ করা হয়েছে এবং ওয়েবসাইটে পাবলিশ হয়েছে!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/<int:id>')
@admin_required
def delete_content(id):
    # যেকোনো কন্টেন্ট (Pending বা Approved) ডিলিট করা
    supabase.table('contents').delete().eq('id', id).execute()
    flash('কন্টেন্টটি সফলভাবে ডিলিট করা হয়েছে।', 'error')
    return redirect(request.referrer or url_for('admin_panel'))
# ==========================================
# অ্যাডমিন পেআউট কন্ট্রোল প্যানেল (Admin Payouts)
# ==========================================
@app.route('/admin/payouts')
@admin_required
def admin_payouts():
    # পেন্ডিং রিকোয়েস্টগুলো ফেচ করা
    pending = supabase.table('payouts').select('*, profiles(username, display_name, email)').eq('status', 'Pending').order('created_at', desc=True).execute().data
    
    # অতীতের পেমেন্ট হিস্ট্রি (Approved / Rejected)
    history = supabase.table('payouts').select('*, profiles(username, display_name, email)').neq('status', 'Pending').order('created_at', desc=True).limit(50).execute().data
    
    return render_template('admin_payouts.html', pending=pending, history=history)


@app.route('/admin/payout/<action>/<int:id>')
@admin_required
def handle_payout(action, id):
    status = 'Approved' if action == 'approve' else 'Rejected'
    supabase.table('payouts').update({'status': status}).eq('id', id).execute()
    flash(f"পেমেন্ট রিকোয়েস্ট {status} করা হয়েছে!", "success" if action == 'approve' else "error")
    return redirect(url_for('admin_payouts'))
    
# শুধুমাত্র লোকাল টেস্টের জন্য, Vercel এটি ইগনোর করবে
if __name__ == '__main__':
    app.run(debug=True, port=5000)
