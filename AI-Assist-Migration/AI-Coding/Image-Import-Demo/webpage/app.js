// Scroll-triggered reveal animations
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, {
    threshold: 0.08,
    rootMargin: '0px 0px -30px 0px'
});

document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const target = document.querySelector(link.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

// Counter animation for tool counts
const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const counts = entry.target.querySelectorAll('.tool-count');
            counts.forEach(el => {
                const target = parseInt(el.textContent, 10);
                let current = 0;
                const step = Math.max(1, Math.floor(target / 10));
                const interval = setInterval(() => {
                    current += step;
                    if (current >= target) {
                        current = target;
                        clearInterval(interval);
                    }
                    el.textContent = current;
                }, 50);
            });
            counterObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.2 });

const toolsGrid = document.querySelector('.tools-grid');
if (toolsGrid) counterObserver.observe(toolsGrid);

// Staggered chain step animation
const chainObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const steps = entry.target.querySelectorAll('.chain-step');
            steps.forEach((step, i) => {
                step.style.opacity = '0';
                step.style.transform = 'translateY(12px)';
                step.style.transition = `opacity 0.4s ease ${i * 0.12}s, transform 0.4s ease ${i * 0.12}s`;
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        step.style.opacity = '1';
                        step.style.transform = 'translateY(0)';
                    });
                });
            });
            chainObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.1 });

document.querySelectorAll('.chain').forEach(chain => chainObserver.observe(chain));
