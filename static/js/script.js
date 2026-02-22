document.addEventListener("DOMContentLoaded", function() {
    
    // --- প্রফেশনাল মোবাইল সাইডবার মেনু (Toggle Menu) ---
    const hamburger = document.getElementById('hamburger');
    const navLinks = document.getElementById('nav-links');

    if (hamburger && navLinks) {
        hamburger.addEventListener('click', (e) => {
            e.stopPropagation(); // ইভেন্ট বাবলিং বন্ধ করা
            navLinks.classList.toggle('active'); 
            hamburger.classList.toggle('toggle-icon'); // ৩ দাগ থেকে ক্রস (X) হবে
        });

        // মেনুর বাইরে ক্লিক করলে মেনু বন্ধ হয়ে যাবে
        document.addEventListener('click', (e) => {
            if (!navLinks.contains(e.target) && !hamburger.contains(e.target)) {
                navLinks.classList.remove('active');
                hamburger.classList.remove('toggle-icon');
            }
        });

        // যেকোনো লিংকে ক্লিক করলে মেনু অটোমেটিক বন্ধ হবে
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navLinks.classList.remove('active');
                hamburger.classList.remove('toggle-icon');
            });
        });
    }

    // --- Flash Message Auto Hide ---
    const flashMessages = document.querySelector('.flash-messages');
    if (flashMessages) {
        setTimeout(() => {
            flashMessages.style.transition = "opacity 0.6s ease, transform 0.6s ease";
            flashMessages.style.opacity = "0";
            flashMessages.style.transform = "translateY(-20px)";
            setTimeout(() => flashMessages.remove(), 600);
        }, 4000);
    }
});
