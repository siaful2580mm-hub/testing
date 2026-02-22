document.addEventListener("DOMContentLoaded", function() {



    // --- Mobile Hamburger Menu Toggle ---
    const hamburger = document.getElementById('hamburger');
    const navLinks = document.getElementById('nav-links');

    if (hamburger && navLinks) {
        hamburger.addEventListener('click', () => {
            navLinks.classList.toggle('active'); // মেনু ওপেন/ক্লোজ হবে
            
            // হ্যামবার্গার আইকন এনিমেশন (Optional, ক্রস চিহ্নের মতো করতে)
            hamburger.classList.toggle('toggle-icon');
        });
    }


    
    // ১. Flash Message Auto Hide (৪ সেকেন্ড পর মেসেজ গায়েব হয়ে যাবে)
    const flashMessages = document.querySelector('.flash-messages');
    if (flashMessages) {
        setTimeout(() => {
            flashMessages.style.transition = "opacity 0.5s ease";
            flashMessages.style.opacity = "0";
            setTimeout(() => flashMessages.remove(), 500);
        }, 4000);
    }

    // ২. Image Upload Preview (আপলোড করার আগে ছবি দেখা)
    const fileInput = document.getElementById('fileInput');
    const imagePreview = document.getElementById('imagePreview');

    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    imagePreview.src = e.target.result;
                    imagePreview.style.display = 'block';
                }
                reader.readAsDataURL(file);
            } else {
                imagePreview.style.display = 'none';
                imagePreview.src = '';
            }
        });
    }

    // ৩. Auto Slug Formatter (ইংরেজিতে স্পেস দিলে হাইফেন বসে যাবে)
    const slugInput = document.getElementById('slugInput');
    if (slugInput) {
        slugInput.addEventListener('input', function() {
            let val = this.value;
            // ইংরেজি বর্ণ, সংখ্যা এবং হাইফেন ছাড়া সব রিমুভ করবে এবং স্পেসকে হাইফেন করবে
            val = val.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
            this.value = val;
        });
    }
});
