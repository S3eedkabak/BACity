import { EventCategory } from "../types/event";

export const categoryImages: Record<string, string> = {
  party:
    "https://images.unsplash.com/photo-1763630053969-77a1d7d85572?auto=format&fit=crop&fm=jpg&q=80&w=1200",
  museum:
    "https://images.unsplash.com/photo-1761563071832-e548e022a706?auto=format&fit=crop&fm=jpg&q=80&w=1200",
  market:
    "https://cdn.sita.sk/sites/32/2018/09/dobry-trh-na-panenskej-2.jpg",
  workshop:
    "https://images.unsplash.com/photo-1770910196320-59fc1254680e?auto=format&fit=crop&fm=jpg&q=80&w=1200",
};

export function imageForCategory(category?: EventCategory | string | null) {
  switch (category) {
    case "Music":
    case "Nightlife":
    case "Festivals":
    case "Comedy":
      return categoryImages.party;
    case "Culture":
    case "Arts":
    case "Theatre":
    case "Exhibitions":
      return categoryImages.museum;
    case "Food & Drink":
    case "Markets":
      return categoryImages.market;
    case "Education":
    case "Workshops":
    case "Technology":
    case "Networking":
    case "Community":
    case "Student":
      return categoryImages.workshop;
    default:
      return categoryImages.party;
  }
}
