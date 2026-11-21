import reflex as rx

ESTILOS_TEMA = rx.html("""
    <style>
        :root, .light, .light-theme {
            color-scheme: light;
            --gray-1: #F4F7F8 !important;
            --gray-2: #EBF0F2 !important;
            --gray-3: #E1E8EC !important;
            --gray-4: #D3DEE3 !important;
            --gray-5: #C5D4DC !important;
            --gray-11: #4A636E !important;
            --gray-12: #1A2E35 !important;
        }
        .dark, .dark-theme, [data-theme="dark"] {
            color-scheme: dark;
            --gray-1: #0D2F3A !important;
            --gray-2: #09242E !important;
            --gray-3: #123C4A !important;
            --gray-4: #174859 !important;
            --gray-5: #1D566B !important;
            --gray-6: #2A718B !important;
            --gray-11: #B8D4DF !important;
            --gray-12: #F0F8FA !important;
        }
    </style>
""")

JS_ZOOM_RESET = """
    const el = document.getElementById('scroll-grafica');
    if (el) { el.scrollLeft = 0; }
    window.dispatchEvent(new Event('resize'));
    requestAnimationFrame(() => {
        const el2 = document.getElementById('scroll-grafica');
        if (el2) { el2.scrollLeft = 0; }
    });
"""

JS_ZOOM_AJUSTAR = """
    const el = document.getElementById('scroll-grafica');
    if (el) {
        const maxScroll = Math.max(0, el.scrollWidth - el.clientWidth);
        if (el.scrollLeft > maxScroll) { el.scrollLeft = maxScroll; }
    }
    window.dispatchEvent(new Event('resize'));
"""