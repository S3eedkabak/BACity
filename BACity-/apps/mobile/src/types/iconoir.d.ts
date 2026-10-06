// The official 7.10.1 declarations give every icon the identical `typeof Icon`
// type. Preserve that exact type for per-icon files, avoiding the 1,600-icon barrel.
declare module 'iconoir-react-native/regular/*' {
  import { Accessibility } from 'iconoir-react-native';
  const Icon: typeof Accessibility;
  export default Icon;
}
declare module 'iconoir-react-native/solid/*' {
  import { Accessibility } from 'iconoir-react-native';
  const Icon: typeof Accessibility;
  export default Icon;
}
