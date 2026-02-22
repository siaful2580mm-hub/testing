import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from supabase import create_client, Client
from dotenv import load_dotenv
from flask import session
from functools import wraps

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
# পাবলিক প্রোফাইল ভিউ (আপডেটেড)
# ==========================================
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


@app.route('/content/<slug>')
def single_content(slug):
    # নির্দিষ্ট Slug দিয়ে কন্টেন্ট আনা
    response = supabase.table('contents').select('*, categories(name_bn)').eq('slug', slug).execute()
    if not response.data:
        abort(404)
    content = response.data[0]
    return render_template('single.html', content=content)

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

            # Supabase এ ডাটা সেভ করা
            new_content = {
                "user_id": session['user']['id'], # <--- মূল সমাধান (এখানে অরিজিনাল ইউজারের আইডি বসবে)
                "title": title,
                "description": description,
                "slug": slug,
                "alt_text": alt_text,
                "category_id": category_id,
                "file_url": file_url,
                "is_approved": False # (টেস্টিংয়ের জন্য True রাখা হলো, পরে অ্যাডমিন প্যানেলের জন্য False করে দিবেন)
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
