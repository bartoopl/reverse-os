export const RETURN_REASONS = [
  { value: "damaged_in_transit", label: "Uszkodzony podczas transportu" },
  { value: "wrong_item_sent", label: "Wysłano zły produkt" },
  { value: "not_as_described", label: "Niezgodny z opisem" },
  { value: "changed_mind", label: "Zmiana decyzji" },
  { value: "defective", label: "Produkt wadliwy" },
  { value: "size_fit_issue", label: "Zły rozmiar / dopasowanie" },
  { value: "quality_issue", label: "Problem z jakością" },
  { value: "duplicate_order", label: "Duplikat zamówienia" },
  { value: "arrived_late", label: "Zbyt późna dostawa" },
  { value: "other", label: "Inny powód" },
];

export const RETURN_METHODS = [
  {
    value: "drop_off_point",
    label: "Paczkomat InPost",
    description: "Nadaj paczkę w dowolnym paczkomacie",
    icon: "📦",
  },
  {
    value: "courier_pickup",
    label: "Kurier pod drzwi",
    description: "Kurier odbierze przesyłkę z podanego adresu",
    icon: "🚚",
  },
  {
    value: "drop_off_post",
    label: "Poczta Polska",
    description: "Nadaj na dowolnej poczcie",
    icon: "✉️",
  },
];

export const ITEM_CONDITIONS = [
  { value: "unopened", label: "Nierozpakowany" },
  { value: "opened_unused", label: "Rozpakowany, nieużywany" },
  { value: "used_good", label: "Używany, dobry stan" },
  { value: "used_damaged", label: "Używany, uszkodzony" },
];

export const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft:                { label: "Szkic",                   color: "text-gray-500" },
  pending:              { label: "Oczekuje",                color: "text-yellow-600" },
  requires_inspection:  { label: "Wymaga weryfikacji",      color: "text-orange-600" },
  approved:             { label: "Zatwierdzony",            color: "text-green-600" },
  rejected:             { label: "Odrzucony",               color: "text-red-600" },
  label_generated:      { label: "Etykieta wygenerowana",   color: "text-blue-600" },
  in_transit:           { label: "W drodze",                color: "text-blue-600" },
  received:             { label: "Otrzymany",               color: "text-purple-600" },
  refund_initiated:     { label: "Zwrot inicjowany",        color: "text-purple-600" },
  refunded:             { label: "Zwrot wykonany",          color: "text-green-700" },
  store_credit_issued:  { label: "Kredyt wystawiony",       color: "text-green-700" },
  keep_it:              { label: "Zatrzymaj produkt",        color: "text-green-700" },
  closed:               { label: "Zamknięty",               color: "text-gray-500" },
  cancelled:            { label: "Anulowany",               color: "text-gray-500" },
};
