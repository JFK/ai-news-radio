import { useTranslation } from "react-i18next";

export default function LanguageSwitcher() {
  const { i18n } = useTranslation();

  const toggle = () => {
    const next = i18n.language === "en" ? "ja" : "en";
    i18n.changeLanguage(next);
    localStorage.setItem("lang", next);
  };

  return (
    <button
      onClick={toggle}
      className="px-2 py-1 text-xs font-medium border border-gray-300 rounded-md text-gray-600 hover:bg-gray-100 cursor-pointer"
    >
      {i18n.language === "en" ? "日本語" : "English"}
    </button>
  );
}
