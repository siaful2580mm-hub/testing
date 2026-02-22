import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from supabase import create_client, Client
from dotenv import load_dotenv
from flask import session
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session, Response

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
# ==========================================
# ইউজার পেআউট ও হিস্ট্রি (User Payout & History)
# ==========================================
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
# ইনসাইট ও আয় (Insight & Earning) রাউট
# ==========================================
@app.route('/insight')
@login_required
def user_insight():
    user_id = session['user']['id']
    
    # ইউজারের আপলোড করা সব কন্টেন্ট ফেচ করা
    res = supabase.table('contents').select('title, slug, views, downloads, file_url, is_approved, created_at').eq('user_id', user_id).order('created_at', desc=True).execute()
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
# পাবলিক প্রোফাইল ভিউ (আপডেটেড)
# ==========================================

# ==========================================
# সিঙ্গেল ইমেজ/কন্টেন্ট ডিটেইলস পেজ
# ==========================================
@app.route('/content/<slug>')
def single_content(slug):
    # ১. কন্টেন্ট ফেচ করা
    res = supabase.table('contents').select('*, categories(name_bn), profiles(username, display_name, avatar_url)').eq('slug', slug).execute()
    if not res.data:
        abort(404)
    
    content = res.data[0]
    content_id = content['id']

    # ২. স্মার্ট ভিউ (View) কাউন্টার (এক ডিভাইসে/সেশনে মাত্র একবার কাউন্ট হবে)
    viewed_items = session.get('viewed_items', []) # সেশন থেকে দেখা আইটেমগুলোর লিস্ট নেওয়া
    
    if content_id not in viewed_items:
        # যদি ইউজার এই ছবিটি আগে না দেখে থাকে, তবেই ভিউ ১ বাড়বে
        new_views = content.get('views', 0) + 1
        supabase.table('contents').update({'views': new_views}).eq('id', content_id).execute()
        content['views'] = new_views
        
        # সেশনে ছবির আইডি সেভ করে রাখা হচ্ছে, যাতে রিফ্রেশ করলে আর না বাড়ে
        viewed_items.append(content_id)
        session['viewed_items'] = viewed_items
        session.modified = True  # ফ্লাস্ককে জানানো হলো যে সেশন আপডেট হয়েছে
    else:
        # রিফ্রেশ করলে ডাটাবেসে আর আপডেট হবে না, শুধু বর্তমান ভিউ সংখ্যাটাই দেখাবে
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

    # ৫. রিলেটেড কন্টেন্ট (একই ক্যাটাগরির অন্য ছবি)
    related = supabase.table('contents').select('*, categories(name_bn)').eq('category_id', content['category_id']).eq('is_approved', True).neq('id', content_id).limit(4).execute().data

    return render_template('single.html', content=content, likes_count=likes_count, user_liked=user_liked, comments=comments, related=related)
@app.route('/profile/<username>')
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
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Supabase এ নতুন ইউজার তৈরি
            res = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {"username": username} # ইউজারের নাম সেভ রাখা
                }
            })
            flash("রেজিস্ট্রেশন সফল হয়েছে! দয়া করে লগইন করুন।", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"ত্রুটি: {str(e)}", "error")
            return redirect(request.url)

    return render_template('signup.html')

# ==========================================
# লগইন (Login) রাউট
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Supabase Auth দিয়ে লগইন চেক
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            
            # ফ্লাস্ক সেশনে (Session) ইউজারের তথ্য সেভ করে রাখা
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
# আপলোড রাউট (সঠিক User ID সহ)
# ==========================================
@app.route('/upload', methods=['GET', 'POST'])
@login_required   # এই ডেকোরেটরটি নিশ্চিত করবে যে ইউজার লগইন করা আছে
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

            # ফাইলের এক্সটেনশন বের করা (যেমন: JPG, PNG)
            file_format = file.filename.rsplit('.', 1)[1].upper() if '.' in file.filename else 'JPG'

            new_content = {
                "user_id": session['user']['id'],
                "title": title,
                "description": description,
                "slug": slug,
                "alt_text": alt_text,
                "category_id": category_id,
                "file_url": file_url,
                "file_format": file_format, # <--- নতুন যুক্ত করা হলো
                "is_approved": False 
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
# অ্যাডমিন প্যানেল ভিউ

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
@app.route('/admin')
@admin_required
def admin_panel():
    # যেসব কন্টেন্ট এখনো অ্যাপ্রুভ হয়নি, সেগুলো ফেচ করা
    res = supabase.table('contents').select('*, categories(name_bn), profiles(username, display_name)').eq('is_approved', False).order('created_at', desc=True).execute()
    return render_template('admin.html', pending_contents=res.data)

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
    # কন্টেন্ট রিজেক্ট বা ডিলিট করা
    supabase.table('contents').delete().eq('id', id).execute()
    flash('কন্টেন্টটি ডিলিট করা হয়েছে।', 'error')
    return redirect(url_for('admin_panel'))
# শুধুমাত্র লোকাল টেস্টের জন্য, Vercel এটি ইগনোর করবে
if __name__ == '__main__':
    app.run(debug=True, port=5000)
