// Remove theme toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    // Add smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Get all buttons that should redirect to onboarding
    const onboardingButtons = document.querySelectorAll('.btn-get-started, .btn-primary');
    
    onboardingButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = 'onboarding.html';
        });
    });

    // Handle onboarding form if we're on the onboarding page
    const onboardingForm = document.getElementById('onboardingForm');
    if (onboardingForm) {
        // Handle category button selection
        const categoryButtons = document.querySelectorAll('.category-btn');
        categoryButtons.forEach(button => {
            button.addEventListener('click', function() {
                this.classList.toggle('selected');
            });
        });

        // Handle summary button selection
        const summaryButtons = document.querySelectorAll('.summary-btn');
        summaryButtons.forEach(button => {
            button.addEventListener('click', function() {
                // Remove selected class from all summary buttons
                summaryButtons.forEach(btn => btn.classList.remove('selected'));
                // Add selected class to clicked button
                this.classList.add('selected');
            });
        });

        // Handle form submission
        onboardingForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Validate form
            const name = document.getElementById('name').value;
            const phone = document.getElementById('phone').value;
            const selectedCategories = document.querySelectorAll('.category-btn.selected');
            const selectedSummary = document.querySelector('.summary-btn.selected');
            const notificationTime = document.getElementById('notification-time').value;

            if (!name || !phone || selectedCategories.length === 0 || !selectedSummary || !notificationTime) {
                alert('Please fill in all required fields and make your selections.');
                return;
            }

            // Hide form and show curating message
            onboardingForm.style.display = 'none';
            document.getElementById('curatingMessage').style.display = 'block';

            // Here you would typically send the data to your backend
            // For now, we'll just simulate a delay
            setTimeout(() => {
                // Redirect to main page or dashboard
                window.location.href = 'index.html';
            }, 3000);
        });
    }
}); 