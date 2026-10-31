"""Shared Tk error explanation with actionable cause/remedy, no automatic data changes.

Single user-visible modal for blocking UI operations; bulk-file failures remain in log.
Never trigger repair commands without a separate, verified user action.
"""
from __future__ import annotations
from tkinter import messagebox

_NATIVE_SHOWERROR = messagebox.showerror
_INSTALLED = False


def explain(title, message):
    txt=str(message or '')
    lower=(str(title)+' '+txt).casefold()
    if 'sha' in lower or 'kimlik' in lower or 'kaynak değiş' in lower:
        return ('Güvenlik kontrolü: kaynak veya maske kimliği uyuşmuyor.',
                'Dosyayı yeniden yükleyin ve şablonun mevcut sürümünü inceleyin. Eski onayı zorla kullanmayın.')
    if 'maske' in lower or 'petek' in lower or 'baskı alanı' in lower:
        return ('PETEK maskesi veya baskı alanı hazır değil / doğrulanamadı.',
                'Önce 4 köşe önerisini doğrulayın, sonra “2. Otomatik Maske Taslağı”nı çalıştırıp yeşil alanı inceleyin. Onaylı maskeyi otomatik değiştirmeyin.')
    if '4k' in lower or 'esrgan' in lower or 'gpu' in lower or 'vulkan' in lower:
        return ('4K motoru, model dosyası veya GPU erişimiyle ilgili bir sorun olabilir.',
                'Seri Üretim > “4K Kurulumunu Kontrol Et” seçeneğini çalıştırın. 4K kapalı normal üretim devam edebilir.')
    if '8080' in lower or '8090' in lower or 'port' in lower:
        return ('İnceleme servisi açık veya port başka bir işlem tarafından kullanılıyor.',
                'Şablon kaydını tamamlayın; uygulamadaki güvenli servis kapatma düğmesini kullanın. Görev Yöneticisi’nden rastgele süreç kapatmayın.')
    if 'excel' in lower or 'xlsx' in lower or 'mağaza' in lower:
        return ('Excel/mağaza verisi veya dosya erişimi tamamlanamadı.',
                'XLSX dosyasının başka programda açık olmadığını ve mağaza profilinin seçildiğini doğrulayın; yeniden denemeden önce çıktıyı yedekleyin.')
    if 'internet' in lower or 'https' in lower or 'yükle' in lower or 'token' in lower:
        return ('İnternet bağlantısı veya bulut yükleme yetkisi başarısız olabilir.',
                'Bağlantı/izinleri kontrol edin; API anahtarlarını rapora eklemeyin. Normal yerel çıktı korunur.')
    if 'dosya' in lower or 'klasör' in lower or 'path' in lower or 'izin' in lower:
        return ('Gerekli dosya veya klasöre erişim başarısız.',
                'Ana çalışma klasörünü kontrol edin; açık dosyayı kapatın ve klasör iznini doğrulayın. Orijinal yedekleri taşımayın.')
    return ('İşlem beklenmedik şekilde tamamlanamadı.',
            'Tekrar denemeden önce açık kayıtlarınızı koruyun. Test Merkezi > Sorun Var bölümüne hata metnini ve ekran adını kaydedin.')


def showerror(title, message, **kwargs):
    cause,remedy=explain(title,message)
    text=(str(message)+'\n\nNEDEN: '+cause+'\n\nNE YAPMALIYIM? '+remedy+
          '\n\nSorun devam ederse bu mesajı “Yapmam Gereken Testler”de Sorun Var olarak kaydedin.')
    return _NATIVE_SHOWERROR(title,text,**kwargs)


def install_global_error_advisor():
    """Cover existing Tk modules using tkinter.messagebox without rewriting them.

    Only showerror is patched: informational dialogs and yes/no confirmations are
    deliberately unaffected. Installation is idempotent, and the native Tk call
    was captured before patching to avoid recursion.
    """
    global _INSTALLED
    if not _INSTALLED:
        messagebox.showerror=showerror
        _INSTALLED=True

