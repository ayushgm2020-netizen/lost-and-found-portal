// SmartRecover Main JavaScript

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Lucide Icons if available
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // 2. Auto-dismiss flash messages after 6 seconds
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(msg => {
        const closeBtn = msg.querySelector('.flash-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                msg.style.opacity = '0';
                msg.style.transform = 'translateY(-6px)';
                setTimeout(() => msg.remove(), 250);
            });
        }
        setTimeout(() => {
            if (msg && msg.parentNode) {
                msg.style.opacity = '0';
                msg.style.transform = 'translateY(-6px)';
                setTimeout(() => msg.remove(), 250);
            }
        }, 6000);
    });

    // 3. Image Upload Preview Handler
    const imageInput = document.getElementById('photo-input');
    const previewContainer = document.getElementById('upload-preview-container');
    const previewImg = document.getElementById('upload-preview-img');
    const uploadPrompt = document.getElementById('upload-prompt');

    if (imageInput && previewImg && previewContainer) {
        imageInput.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (file) {
                // Validate size (5MB max)
                if (file.size > 5 * 1024 * 1024) {
                    alert('File size exceeds the 5MB limit. Please select a smaller image.');
                    this.value = '';
                    return;
                }
                const reader = new FileReader();
                reader.onload = function (event) {
                    previewImg.src = event.target.result;
                    previewContainer.style.display = 'block';
                    if (uploadPrompt) uploadPrompt.style.display = 'none';
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // 4. Client-side Instant Filter for Items if element exists
    const searchInput = document.getElementById('live-search-input');
    const itemCards = document.querySelectorAll('.browse-item-card');
    const categoryFilter = document.getElementById('category-filter');
    const typeFilter = document.getElementById('type-filter');

    function applyItemFilters() {
        if (!itemCards.length) return;
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const selectedCategory = categoryFilter ? categoryFilter.value.toLowerCase() : '';
        const selectedType = typeFilter ? typeFilter.value.toLowerCase() : '';

        let visibleCount = 0;
        itemCards.forEach(card => {
            const title = card.getAttribute('data-name') || '';
            const category = card.getAttribute('data-category') || '';
            const type = card.getAttribute('data-type') || '';
            const location = card.getAttribute('data-location') || '';

            const matchesQuery = !query || title.includes(query) || location.includes(query);
            const matchesCategory = !selectedCategory || category === selectedCategory;
            const matchesType = !selectedType || type === selectedType;

            if (matchesQuery && matchesCategory && matchesType) {
                card.style.display = 'flex';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        const noResultsEl = document.getElementById('no-filter-results');
        if (noResultsEl) {
            noResultsEl.style.display = (visibleCount === 0) ? 'block' : 'none';
        }
    }

    if (searchInput) searchInput.addEventListener('input', applyItemFilters);
    if (categoryFilter) categoryFilter.addEventListener('change', applyItemFilters);
    if (typeFilter) typeFilter.addEventListener('change', applyItemFilters);

    // 5. Modal Helpers
    window.openModal = function (modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'flex';
        }
    };

    window.closeModal = function (modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    };
});
