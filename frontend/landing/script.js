document.addEventListener('DOMContentLoaded', () => {

  // --- Button Alert Functionality ---
  const getStartedBtn = document.getElementById('getStartedBtn');
  if (getStartedBtn) {
    getStartedBtn.addEventListener('click', () => {
      // Replace the alert with this line to redirect
      window.location.href = '/auth/login'; // <-- CHANGE THIS URL
    });
  }

  // --- Scroll Animation Functionality ---
  const fadeElems = document.querySelectorAll('.fade-in');

  const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
  };

  const observer = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  fadeElems.forEach(elem => {
    observer.observe(elem);
  });
  
  // --- NEW: Dummy Contact Form Submission ---
  const contactForm = document.getElementById('contactForm');
  if (contactForm) {
    contactForm.addEventListener('submit', (event) => {
      // Prevent the default form submission (which reloads the page)
      event.preventDefault();
      
      // Show a confirmation message
      alert('Thank you for your message! We will get back to you shortly.');
      
      // Optional: Clear the form fields after submission
      contactForm.reset();
    });
  }
  // --- END NEW ---

});