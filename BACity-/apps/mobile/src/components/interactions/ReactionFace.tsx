import Svg, { Circle, Path } from "react-native-svg";
/** Code-native reaction faces; no font-dependent emoji or raster assets. */
export function ReactionFace({
  rating,
  color,
}: {
  rating: number;
  color: string;
}) {
  const mouth =
    rating === 5
      ? "M7 12h10a5 5 0 0 1-10 0Z"
      : rating === 4
        ? "M7.5 13.5q4.5 5 9 0"
        : rating === 2
          ? "M7.5 17q4.5-5 9 0"
          : "M8 16q4-4 8 0";
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" aria-hidden={true}>
      <Circle
        cx={12}
        cy={12}
        r={9}
        stroke={color}
        strokeWidth={1.6}
        fill="none"
      />
      {rating === 5 ? (
        <Path
          d="M7 9q1.5-2 3 0m4 0q1.5-2 3 0"
          stroke={color}
          strokeWidth={1.6}
          fill="none"
        />
      ) : (
        <>
          <Circle cx={8.5} cy={9.5} r={0.9} fill={color} />
          <Circle cx={15.5} cy={9.5} r={0.9} fill={color} />
        </>
      )}
      {rating === 1 && (
        <Path
          d="m7 6 3 1.5m7-1.5-3 1.5"
          stroke={color}
          strokeWidth={1.6}
          fill="none"
        />
      )}
      <Path
        d={mouth}
        fill="none"
        stroke={color}
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
