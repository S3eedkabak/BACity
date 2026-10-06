import Activity from 'iconoir-react-native/regular/Activity';
import Album from 'iconoir-react-native/regular/Album';
import AntennaSignal from 'iconoir-react-native/regular/AntennaSignal';
import ArrowRight from 'iconoir-react-native/regular/ArrowRight';
import ArrowUp from 'iconoir-react-native/regular/ArrowUp';
import ArrowUpRight from 'iconoir-react-native/regular/ArrowUpRight';
import Bell from 'iconoir-react-native/regular/Bell';
import Book from 'iconoir-react-native/regular/Book';
import Bookmark from 'iconoir-react-native/regular/Bookmark';
import BookmarkSolid from 'iconoir-react-native/solid/Bookmark';
import Building from 'iconoir-react-native/regular/Building';
import Calendar from 'iconoir-react-native/regular/Calendar';
import Camera from 'iconoir-react-native/regular/Camera';
import ChatBubble from 'iconoir-react-native/regular/ChatBubble';
import ChatLines from 'iconoir-react-native/regular/ChatLines';
import Check from 'iconoir-react-native/regular/Check';
import CheckCircle from 'iconoir-react-native/regular/CheckCircle';
import CheckCircleSolid from 'iconoir-react-native/solid/CheckCircle';
import Circle from 'iconoir-react-native/regular/Circle';
import Clock from 'iconoir-react-native/regular/Clock';
import CloudXmark from 'iconoir-react-native/regular/CloudXmark';
import Community from 'iconoir-react-native/regular/Community';
import Download from 'iconoir-react-native/regular/Download';
import EditPencil from 'iconoir-react-native/regular/EditPencil';
import Filter from 'iconoir-react-native/regular/Filter';
import Gps from 'iconoir-react-native/regular/Gps';
import Group from 'iconoir-react-native/regular/Group';
import HalfMoon from 'iconoir-react-native/regular/HalfMoon';
import Heart from 'iconoir-react-native/regular/Heart';
import HeartSolid from 'iconoir-react-native/solid/Heart';
import HomeSimple from 'iconoir-react-native/regular/HomeSimple';
import InfoCircle from 'iconoir-react-native/regular/InfoCircle';
import Key from 'iconoir-react-native/regular/Key';
import Label from 'iconoir-react-native/regular/Label';
import Lock from 'iconoir-react-native/regular/Lock';
import LogOut from 'iconoir-react-native/regular/LogOut';
import Map from 'iconoir-react-native/regular/Map';
import MapPin from 'iconoir-react-native/regular/MapPin';
import Menu from 'iconoir-react-native/regular/Menu';
import Minus from 'iconoir-react-native/regular/Minus';
import MoreHoriz from 'iconoir-react-native/regular/MoreHoriz';
import MusicDoubleNote from 'iconoir-react-native/regular/MusicDoubleNote';
import NavArrowDown from 'iconoir-react-native/regular/NavArrowDown';
import NavArrowLeft from 'iconoir-react-native/regular/NavArrowLeft';
import NavArrowRight from 'iconoir-react-native/regular/NavArrowRight';
import NavArrowUp from 'iconoir-react-native/regular/NavArrowUp';
import Navigator from 'iconoir-react-native/regular/Navigator';
import Network from 'iconoir-react-native/regular/Network';
import NetworkRight from 'iconoir-react-native/regular/NetworkRight';
import OpenNewWindow from 'iconoir-react-native/regular/OpenNewWindow';
import Page from 'iconoir-react-native/regular/Page';
import Palette from 'iconoir-react-native/regular/Palette';
import Plus from 'iconoir-react-native/regular/Plus';
import PlusCircle from 'iconoir-react-native/regular/PlusCircle';
import Prohibition from 'iconoir-react-native/regular/Prohibition';
import Search from 'iconoir-react-native/regular/Search';
import Settings from 'iconoir-react-native/regular/Settings';
import ShareIos from 'iconoir-react-native/regular/ShareIos';
import Shield from 'iconoir-react-native/regular/Shield';
import ShieldCheck from 'iconoir-react-native/regular/ShieldCheck';
import Sparks from 'iconoir-react-native/regular/Sparks';
import Star from 'iconoir-react-native/regular/Star';
import SunLight from 'iconoir-react-native/regular/SunLight';
import ThumbsDown from 'iconoir-react-native/regular/ThumbsDown';
import ThumbsUp from 'iconoir-react-native/regular/ThumbsUp';
import Tools from 'iconoir-react-native/regular/Tools';
import TriangleFlag from 'iconoir-react-native/regular/TriangleFlag';
import User from 'iconoir-react-native/regular/User';
import ViewGrid from 'iconoir-react-native/regular/ViewGrid';
import WarningCircle from 'iconoir-react-native/regular/WarningCircle';
import WarningTriangle from 'iconoir-react-native/regular/WarningTriangle';
import Wifi from 'iconoir-react-native/regular/Wifi';
import Xmark from 'iconoir-react-native/regular/Xmark';
import XmarkCircle from 'iconoir-react-native/regular/XmarkCircle';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';

// Semantic compatibility keys keep existing navigation/action contracts unchanged.
const icons = {
  'camera-outline': Camera,
  'add-outline': Plus,
  'download-outline': Download,
  'warning-outline': WarningTriangle,
  'document-text-outline': Page,
  'chatbubbles-outline': ChatLines,
  'add': Plus,
  'add-circle-outline': PlusCircle,
  'albums-outline': Album,
  'alert': WarningTriangle,
  'alert-circle-outline': WarningCircle,
  'arrow-forward': ArrowRight,
  'arrow-up': ArrowUp,
  'arrow-up-outline': ArrowUpRight,
  'ban-outline': Prohibition,
  'bookmark': BookmarkSolid,
  'bookmark-outline': Bookmark,
  'business-outline': Building,
  'calendar': Calendar,
  'calendar-outline': Calendar,
  'chatbubble-ellipses-outline': ChatLines,
  'chatbubble-outline': ChatBubble,
  'checkmark': Check,
  'checkmark-circle': CheckCircleSolid,
  'checkmark-circle-outline': CheckCircle,
  'chevron-back': NavArrowLeft,
  'chevron-down': NavArrowDown,
  'chevron-forward': NavArrowRight,
  'chevron-up': NavArrowUp,
  'close': Xmark,
  'close-circle': XmarkCircle,
  'close-circle-outline': XmarkCircle,
  'cloud-offline-outline': CloudXmark,
  'color-palette-outline': Palette,
  'construct-outline': Tools,
  'create-outline': EditPencil,
  'ellipse-outline': Circle,
  'ellipsis-horizontal': MoreHoriz,
  'flag-outline': TriangleFlag,
  'git-branch-outline': NetworkRight,
  'git-network-outline': Network,
  'grid-outline': ViewGrid,
  'heart': HeartSolid,
  'heart-outline': Heart,
  'home': HomeSimple,
  'home-outline': HomeSimple,
  'information-circle-outline': InfoCircle,
  'key-outline': Key,
  'library-outline': Book,
  'locate': Gps,
  'locate-outline': Gps,
  'location': MapPin,
  'location-outline': MapPin,
  'lock-closed-outline': Lock,
  'log-out-outline': LogOut,
  'map': Map,
  'map-outline': Map,
  'menu-outline': Menu,
  'moon': HalfMoon,
  'moon-outline': HalfMoon,
  'musical-notes-outline': MusicDoubleNote,
  'navigate': Navigator,
  'navigate-outline': Navigator,
  'notifications': Bell,
  'notifications-outline': Bell,
  'open': OpenNewWindow,
  'options-outline': Filter,
  'people': Group,
  'people-circle-outline': Community,
  'people-outline': Group,
  'person': User,
  'person-outline': User,
  'pricetag-outline': Label,
  'pulse-outline': Activity,
  'radio-outline': AntennaSignal,
  'remove': Minus,
  'remove-outline': Minus,
  'search': Search,
  'search-outline': Search,
  'settings-outline': Settings,
  'share-outline': ShareIos,
  'shield-checkmark-outline': ShieldCheck,
  'shield-outline': Shield,
  'sparkles': Sparks,
  'sparkles-outline': Sparks,
  'star-outline': Star,
  'sunny-outline': SunLight,
  'thumbs-down-outline': ThumbsDown,
  'thumbs-up-outline': ThumbsUp,
  'time': Clock,
  'wifi': Wifi,
} as const;
export type AppIconName = keyof typeof icons;
export function AppIcon({ name, size = tokens.icon.standard, color = colors.text, strokeWidth = 1.7 }: { name: AppIconName; size?: number; color?: string; strokeWidth?: number }) {
  const Icon = icons[name];
  return <Icon width={size} height={size} color={color} strokeWidth={strokeWidth} />;
}

