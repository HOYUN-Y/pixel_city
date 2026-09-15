import {readFile} from 'node:fs/promises';
import {createGuide,httpHandler} from '../server/guide.mjs';
const {places}=JSON.parse(await readFile(new URL('../assets/city_pilot/places.json',import.meta.url)));
export default httpHandler(createGuide({places}));
